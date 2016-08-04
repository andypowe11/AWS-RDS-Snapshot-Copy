from __future__ import print_function
from datetime import tzinfo, timedelta, datetime
import time
from boto3 import client
import json

# Lambda function that makes a manual copy of the most recent
# auto snapshot for one or more RDS instances, shares it with a
# 'restricted' Failsafe account, sends an SNS notification
# and then tidies up after itself.

# List of database identifiers
INSTANCES = ["db-name1", "db-name2"]

# AWS region in which the db instances exist
REGION = "eu-west-1"

# The account to share Failsafe snapshots with
SHAREWITH = "012345678901"

# SNS topic ARN to announce availability of the manual snapshot copy
SNSARN = "arn:aws:sns:eu-west-1:012345678901:rds-copy-snapshots"

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

def create_manual_copy(rds, instance):
    print("Creating manual copy of the most recent auto snapshot of {}".format(instance))
    autos = get_snaps(rds, instance, 'automated')
    newest = autos[-1]
    newestname = newest['DBSnapshotIdentifier']
    failsafename = "failsafe-"+newest['DBSnapshotIdentifier'][4:]
    manualexists = False
    manuals = get_snaps(rds, instance, 'manual')
    for manual in manuals:
        if manual['DBSnapshotIdentifier'] == failsafename:
            print("Manual snapshot already exists for auto snapshot {}".format(newestname))
            return
    rds.copy_db_snapshot(
        SourceDBSnapshotIdentifier=newestname,
        TargetDBSnapshotIdentifier=failsafename
    )
    wait_until_available(rds, instance, failsafename)
    print("Snapshot {} copied to {}".format(newestname, failsafename))
    share_snapshot(rds, failsafename)
    send_sns(instance, failsafename)
    
def send_sns(instance, failsafename):
    if SNSARN:
        print("Sending SNS alert")
        message = {"Instance": instance, "FailsafeSnapshotID": failsafename}
        sns = client("sns", region_name=REGION)
        response = sns.publish(
            TargetArn=SNSARN,
            Message=json.dumps({'default': json.dumps(message)}),
            MessageStructure='json'
        )
        
def share_snapshot(rds, failsafename):
    if SHAREWITH:
        print("Sharing {}".format(failsafename))
        rds.modify_db_snapshot_attribute(
            DBSnapshotIdentifier=failsafename,
            AttributeName='restore',
            ValuesToAdd=[
                SHAREWITH
            ]
        )

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
    
def delete_old_manuals(rds, instance):
    print("Deleting old manual snapshots for {}".format(instance))
    manuals = get_snaps(rds, instance, 'manual')
    for manual in manuals:
        # Only check Failsafe manual snapshots
        if manual['DBSnapshotIdentifier'][:9] != "failsafe-":
            print("Ignoring {}".format(manual['DBSnapshotIdentifier']))
            continue
        print("Deleting {}".format(manual['DBSnapshotIdentifier']))
        rds.delete_db_snapshot(
            DBSnapshotIdentifier=manual['DBSnapshotIdentifier']
        )

def get_snap_date(snap):
    # If snapshot is still being created it doesn't have a SnapshotCreateTime
    if snap['Status'] != "available":
        return datetime.now(utc)
    else:
        return snap['SnapshotCreateTime']

def get_snaps(rds, instance, snap_type):
    snapshots = rds.describe_db_snapshots(
                SnapshotType=snap_type,
                DBInstanceIdentifier=instance)['DBSnapshots']
    if len(snapshots) > 0:
        snapshots = sorted(snapshots, key=get_snap_date)
    return snapshots

def handler(event, context):
    rds = client("rds", region_name=REGION)

    if INSTANCES:
        for instance in INSTANCES:
            delete_old_manuals(rds, instance)
            create_manual_copy(rds, instance)
    else:
        print("You must populate the INSTANCES variable.")
