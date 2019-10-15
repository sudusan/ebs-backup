# Backup all in-use volumes in all regions

import boto3
import datetime
import os
import collections

ec2 = boto3.client('ec2')
ssm = boto3.client('ssm')

def lambda_handler(event, context):
    
    application_name = os.environ['APPLICATION_NAME']
    environment = os.environ['ENVIRONMENT']
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
            #if device_name == '/dev/xvda':
            #    continue
            print ("Found EBS volume %s on instance %s" % (
                vol_id, instance['InstanceId']))

            snap = ec.create_snapshot(
                VolumeId=vol_id,
            )

            # add snapshot id to parameter store
            snapid = snap['SnapshotId']
            parameterName = '/' + application_name + '/' + environment + device_name 
            print("Parameter Name: %s" %(parameterName))
            try:
                ssm.delete_parameter(Name=parameterName)
            except:
                print("Parameter Name: %s not found" %(parameterName))
            ssm.put_parameter(Name=parameterName, Value=snapid, Overwrite=True, Type='String')

            to_tag[retention_days].append(snap['SnapshotId'])

            print ("Retaining snapshot %s of volume %s from instance %s for %d days" % (
                snap['SnapshotId'],
                vol_id,
                instance['InstanceId'],
                retention_days,
            ))

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