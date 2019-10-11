# Backup all in-use volumes in all regions

import boto3
import datetime
import os
import collections
import time

ec2 = boto3.client('ec2')

def update_asg(asgName, snapid):
    # get autoscaling client
    client = boto3.client('autoscaling')
    # get object for the ASG we're going to update, filter by name of target ASG
    response = client.describe_auto_scaling_groups(AutoScalingGroupNames=[asgName])
    if not response['AutoScalingGroups']:
        return 'No such ASG'
    
    # get name of InstanceID in current ASG that we'll use to model new Launch Configuration after
    sourceInstanceId = response.get('AutoScalingGroups')[0]['Instances'][0]['InstanceId']

    # get block device mapping (by default boto doesn't copy this)
    sourceLaunchConfig = response.get('AutoScalingGroups')[0]['LaunchConfigurationName']
    print('current launch config name:' + sourceLaunchConfig)
    responseLC = client.describe_launch_configurations(LaunchConfigurationNames=[sourceLaunchConfig])
    sourceBlockDevices = responseLC.get('LaunchConfigurations')[0]['BlockDeviceMappings']
    for idx, dev in enumerate(sourceBlockDevices):
        print(dev)
        dev_name = dev['DeviceName']
        if dev_name == '/dev/xvda':
            continue
        sourceBlockDevices[idx]['Ebs']['SnapshotId'] = snapid[dev_name][0]

    # create LC using instance from target ASG as a template, only diff is the name of the new LC and new AMI
    timeStamp = time.time()
    timeStampString = datetime.datetime.fromtimestamp(timeStamp).strftime('%Y-%m-%d-%H-%M-%S')
    newLaunchConfigName = asgName + '_' + timeStampString
    print('new launch config name: ' + newLaunchConfigName)
    client.create_launch_configuration(
        InstanceId = sourceInstanceId,
        LaunchConfigurationName=newLaunchConfigName,
        BlockDeviceMappings = sourceBlockDevices )

    # update ASG to use new LC
    response = client.update_auto_scaling_group(AutoScalingGroupName = asgName,LaunchConfigurationName = newLaunchConfigName)

    return 'Updated ASG `%s` with new launch configuration `%s``.' % (asgName, newLaunchConfigName)



def lambda_handler(event, context):
    
    targetASG = os.environ['ASG_NAME']
    ec = boto3.client('ec2')
    reservations = ec.describe_instances(
        Filters=[
            {'Name': 'tag-key', 'Values': ['Backup', 'Backup']},
        ]
    ).get(
        'Reservations', []
    )

    instances = sum(
        [
            [i for i in r['Instances']]
            for r in reservations
        ], [])

    print ("Found %d instances that need backing up" % len(instances))

    to_tag = collections.defaultdict(list)
    to_snap = collections.defaultdict(list)

    for instance in instances:
        try:
            retention_days = [
                int(t.get('Value')) for t in instance['Tags']
                if t['Key'] == 'Retention'][0]
        except IndexError:
            retention_days = 7

        for dev in instance['BlockDeviceMappings']:
            if dev.get('Ebs', None) is None:
                continue
            vol_id = dev['Ebs']['VolumeId']
            device_name = dev['DeviceName']
            if device_name == '/dev/xvda':
                continue
            print ("Found EBS volume %s on instance %s" % (
                vol_id, instance['InstanceId']))

            snap = ec.create_snapshot(
                VolumeId=vol_id,
            )
            # update autoscaling group's launch config with new snapshot id
            snapid = snap['SnapshotId']

            to_tag[retention_days].append(snapid)
            to_snap[device_name].append(snapid)

            print ("Retaining snapshot %s of volume %s from instance %s for %d days" % (
                snap['SnapshotId'],
                vol_id,
                instance['InstanceId'],
                retention_days,
            ))
        asgUpdateResponse = update_asg(targetASG, to_snap)
        print(asgUpdateResponse)
        for retention_days in to_tag.keys():
            delete_date = datetime.date.today() + datetime.timedelta(days=retention_days)
            delete_fmt = delete_date.strftime('%Y-%m-%d')
            print ("Will delete %d snapshots on %s" % (len(to_tag[retention_days]), delete_fmt))
            ec.create_tags(
            Resources=to_tag[retention_days],
            Tags=[
                {'Key': 'DeleteOn', 'Value': delete_fmt},
            ]
        )