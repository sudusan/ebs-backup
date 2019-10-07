from __future__ import print_function

import json
import datetime
import time
import boto3
import os

print('Loading function')

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    # get autoscaling client
    client = boto3.client('autoscaling')
    #clientEc2 = boto3.client('ec2')
    targetASG = os.environ['ASG_NAME']

    # get object for the ASG we're going to update, filter by name of target ASG
    response = client.describe_auto_scaling_groups(AutoScalingGroupNames=[targetASG])

    if not response['AutoScalingGroups']:
        return 'No such ASG'

    # get name of InstanceID in current ASG that we'll use to model new Launch Configuration after
    # sourceInstanceId = response.get('AutoScalingGroups')[0]['Instances'][0]['InstanceId']

    # get block device mapping (by default boto doesn't copy this)
    sourceLaunchConfig = response.get('AutoScalingGroups')[0]['LaunchConfigurationName']
    print('current launch config name:' + sourceLaunchConfig)
    responseLC = client.describe_launch_configurations(LaunchConfigurationNames=[sourceLaunchConfig])
    sourceBlockDevices = responseLC.get('LaunchConfigurations')[0]['BlockDeviceMappings']
    print('Current LC block devices:')
    print(sourceBlockDevices[0]['Ebs'])
    # sourceBlockDevices[0]['Ebs']['SnapshotId'] = sourceAmiSnapshot
    # print('New LC block devices (snapshotID changed):')
    # print(sourceBlockDevices[0]['Ebs'])

    # create LC using instance from target ASG as a template, only diff is the name of the new LC and new AMI
    # timeStamp = time.time()
    # timeStampString = datetime.datetime.fromtimestamp(timeStamp).strftime('%Y-%m-%d-%H-%M-%S')
    # newLaunchConfigName = event['targetASG'] + '_'+ event['newAmiID'] + '_' + timeStampString
    # print('new launch config name: ' + newLaunchConfigName)
    # client.create_launch_configuration(
    #    InstanceId = sourceInstanceId,
    #    LaunchConfigurationName=newLaunchConfigName,
    #    ImageId= event['newAmiID'],
    #    BlockDeviceMappings = sourceBlockDevices )

    # update ASG to use new LC
    #response = client.update_auto_scaling_group(AutoScalingGroupName = event['targetASG'],LaunchConfigurationName = newLaunchConfigName)

    #return 'Updated ASG `%s` with new launch configuration `%s` which includes AMI `%s`.' % (event['targetASG'], newLaunchConfigName, event['newAmiID'])