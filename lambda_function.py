# Backup all in-use volumes in all regions

import boto3
import datetime
import os

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
    ssm = boto3.client('ssm')
    application_name = os.environ['APPLICATION_NAME']
    environment = os.environ['ENVIRONMENT']
    
    # Get list of regions
    regions = ec2.describe_regions().get('Regions',[] )

    # Iterate over regions
    for region in regions:
        print ("Checking region %s " % region['RegionName'])
        reg=region['RegionName']

        # Connect to region
        ec2 = boto3.client('ec2', region_name=reg)
    
        # Get all in-use volumes in all regions  
        result = ec2.describe_volumes( 
            Filters=[
                {'Name': 'status', 
                'Values': ['in-use']
                },
                {'Name': 'tag:Backup', 
                'Values': ['Backup']
                },
        ])
        
        for volume in result['Volumes']:
            print ("Backing up %s in %s" % (volume['VolumeId'], volume['AvailabilityZone']))
        
            # Create snapshot
            result = ec2.create_snapshot(VolumeId=volume['VolumeId'],Description='Created by Lambda backup function ebs-snapshots')
        
            # add snapshot id to parameter store
            
            # Get snapshot resource 
            ec2resource = boto3.resource('ec2', region_name=reg)
            snapshot = ec2resource.Snapshot(result['SnapshotId'])
        
            drivename = 'N/A'
            retention_days = 7
            # Find name tag for volume if it exists
            if 'Tags' in volume:
                for tags in volume['Tags']:
                    if tags["Key"] == 'Drive':
                        drivename = tags["Value"]
                    if tags["Key"] == 'Retention':
                        retention_days = tags["Value"]
            retention_days = int(retention_days)
            delete_date = datetime.date.today() + datetime.timedelta(days=retention_days)
            delete_fmt = delete_date.strftime('%Y-%m-%d')
        
            # Add volume name to snapshot for easier identification
            snapshot.create_tags(Tags=[
                {'Key': 'Drive','Value': drivename},
                {'Key': 'DeleteOn', 'Value': delete_fmt}
                ])
            snapid = result['SnapshotId']
            parameterName = application_name + '-' + environment + '-EBSDRIVE-' + drivename 
            ssm.put_parameter(Name=parameterName, Value=snapid, Overwrite=True, Type='String')
