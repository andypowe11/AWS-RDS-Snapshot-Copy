# AWS RDS Snapshot Copy
Copy RDS snapshots to a second account for safe-keeping
## Background
Disaster recovery (DR) is often thought of in terms of handling massive failures of infrastructure - the
loss of a whole data centre for example.
In AWS, these kinds of failures are usually mitigated by architecting solutions that span
multiple availability zones and regions.
However, there are other kinds of 'disasters' including the accidental or wilfull wholesale deletion of resources
by people who have legitimate access to an AWS account.

This kind of 'disaster' can be mitigated by saving copies of key resources - AMIs, CloudFormation templates,
encryption keys and instance & RDS snapshots - to a second 'failsafe' account to which there is limited
and carefully controlled access. Such control could be maintained by splitting the password and the MFA device across
multiple members of staff, requiring two to be present before access is possible.

The Lambda functions provided here offer a way of taking a daily copy of the most recent automated snapshots from
one or more RDS instances in a Live account to a Failsafe account and can be used as part
of the above strategy.
## Overview
Two Lambda python functions are provided.

The first, rdscopysnappshots.py, runs in the Live account on a daily
basis. It deletes any snapshot copies left over from the previous day's run, creates a new manual copy
of the most recent snapshot for each RDS instance, shares it with the Failsafe account and sends an SNS alert
to indicate that the snapshot is available.

The second function, rdssavesnapshot.py, runs in the Failsafe account and is triggered on receipt of the SNS alert.
It takes a manual copy of the newly shared snapshot and deletes any existing snapshots that are older
than a set age.
## Configuration
The following variables should be configured before use:
### rdscopysnapshot.py
| Variable | Description |
|----------|-------------|
| INSTANCES | A list of RDS instance identifiers for which snapshot copies are to be taken, e.g. ["db-name1", "db-name2"] |
| REGION | The AWS region in which the RDS instances exist, e.g. "eu-west-1" |
| SHAREWITH | The Failsafe account with which snapshots will be shared, e.g. "012345678901" |
| SNSARN | The SNS topic ARN used to announce availability of the manual snapshot copy, e.g.  "arn:aws:sns:eu-west-1:012345678901:rds-copy-snapshots" |
### rdssavesnapshot.py
| Variable | Description |
|----------|-------------|
| REGION | The AWS region in which the database instances exist, e.g.  "eu-west-1" |
| RETENTION | The snapshot retention period in days, e.g. 31 |
## Usage

In the Live account, create a new IAM Role using the rdscopysnapshots-role-policy.json JSON role policy.
Create a new Lambda function using  rdscopysnapshoy.py and trigger it using a daily CloudWatch event.
Associate the new Role with the new Lambda function.
Configure the new Lambda function as described above.

Note that It is safe to test the new function multiple times.

In the Failsafe account, create a new IAM Role using the rdssavesnapshot-role-policy.json JSON role policy.
Create a new Lambda function using rdssavesnapshot.py and trigger it from SNS using the topic configured above.
Associate the new Role with the new Lambda function.
Configure the new Lambda function as described above.

In both cases, the new Lambda functions wait while any snapshot copies are created. This can take several minutes. Set
the timeout on the new Failsafe Lambda function to 5 minutes. Set the timeout on the new Live Lambda function
to at least the same amount - possibly longer if you have configured multiple RDS instances.
## Encryption
These functions have been tested with unencrypted RDS instances. They should work with encrypted RDS instances as well.
However, you will need to share the appropriate KMS
encryption key from the Live account to the Failsafe account prior to use,
as described at http://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ShareSnapshot.html.
## Acknowledgements
Much of the initial thinking for these functions came from Matt Johnson (mhj@amazon.com).

The functions themselves are partly based on the function at https://github.com/xombiemp/rds-copy-snapshots-lambda.
