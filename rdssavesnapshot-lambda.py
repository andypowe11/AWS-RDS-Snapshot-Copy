from __future__ import print_function
from datetime import tzinfo, timedelta, datetime
import time
from boto3 import client
import json
import re

# Lambda function that saves a Failsafe copy of the most recently shared
# snapshot from an RDS instance in a Live account. Initiated on receipt of
# an SNS alert.

# AWS region in which the database instances exist
REGION = "eu-west-1"

# Snapshot retention period in days
RETENTION = 31

# Handle timezones correctly
ZERO = timedelta(0)
class UTC(tzinfo):
  def utcoffset(self, dt):
    return ZERO
  def tzname(self, dt):
    return "UTC"
  def dst(self, dt):
    return ZERO
utc = UTC()

def copy_snapshot(rds, instance, failsafename):
    print("Making local copy of {}".format(failsafename))
    shared = get_snaps(rds, None, 'shared')
    manuals = get_snaps(rds, instance, 'manual')
    if not shared:
        print("Error: No shared snapshots found.")
        return
    delete_before_copy = False
    for manual in manuals:
        if manual['DBSnapshotIdentifier'] == failsafename:
            print("Warning: Local copy already exists - will delete it before copying")
            delete_before_copy = True
    shared_exists = False
    for share in shared:
        print("Checking {}".format(share['DBSnapshotIdentifier']))
        regexp = ".*\:{}".format(re.escape(failsafename))
        if re.match(regexp, share['DBSnapshotIdentifier']):
            if delete_before_copy:
                rds.delete_db_snapshot(
                    DBSnapshotIdentifier=failsafename
                )
            rds.copy_db_snapshot(
                SourceDBSnapshotIdentifier=share['DBSnapshotIdentifier'],
                TargetDBSnapshotIdentifier=failsafename
            )
            wait_until_available(rds, instance, failsafename)
            print("Snapshot {} copied to {}".format(share['DBSnapshotIdentifier'], failsafename))
            shared_exists = True
    if shared_exists == False:
        print("Error: Shared snapshot with id ...:snapshot:{} not found.".format(failsafename))
    
def wait_until_available(rds, instance, snapshot):
    print("Waiting for copy of {} to complete.".format(snapshot))
    available = False
    while not available:
        time.sleep(10)
        manuals = get_snaps(rds, instance, 'manual')
        for manual in manuals:
            if manual['DBSnapshotIdentifier'] == snapshot:
                #print("{}: {}...".format(manual['DBSnapshotIdentifier'], manual['Status']))
                if manual['Status'] == "available":
                    available = True
                    break
    
def get_snap_date(snap):
    # If snapshot is still being created it doesn't have a SnapshotCreateTime
    if snap['Status'] != "available":
        return datetime.now(utc)
    else:
        return snap['SnapshotCreateTime']

def get_snaps(rds, instance, snap_type):
    if instance:
        snapshots = rds.describe_db_snapshots(
                    SnapshotType=snap_type,
                    DBInstanceIdentifier=instance,
                    IncludeShared=True)['DBSnapshots']
    else:
        snapshots = rds.describe_db_snapshots(
                    SnapshotType=snap_type,
                    IncludeShared=True)['DBSnapshots']
    if snapshots:
        snapshots = sorted(snapshots, key=get_snap_date)
    return snapshots
    
def delete_old_snapshots(rds, instance):
    print("Deleting manual snapshots older than {} days".format(RETENTION))
    manuals = get_snaps(rds, instance, 'manual')
    for manual in manuals:
        # Only bother with snapshots that are available
        if manual['Status'] != "available":
            continue
        snap_date = manual['SnapshotCreateTime']
        now = datetime.now(utc)
        snap_age = now - snap_date
        if snap_age.days >= RETENTION:
            print("Deleting: {}".format(manual['DBSnapshotIdentifier']))
            rds.delete_db_snapshot(
                DBSnapshotIdentifier=manual['DBSnapshotIdentifier']
            )
        else:
            print("Not deleting {} (it is only {} days old)".format(manual['DBSnapshotIdentifier'], snap_age.days))

def handler(event, context):
    rds = client("rds", region_name=REGION)

    for record in event['Records']:
        if record['EventSource'] == 'aws:sns' and record['Sns']['Message']:
	        message = json.loads(record['Sns']['Message'])
	        instance = message['Instance']
	        snap_id = message['FailsafeSnapshotID']
	        print("Instance: {}".format(instance))
	        print("FailsafeSnapshotID: {}".format(snap_id))

    if instance and snap_id:
        copy_snapshot(rds, instance, snap_id)
        delete_old_snapshots(rds, instance)
    else:
        print("Error: Instance and FailsafeSnapshotID not provided.")
