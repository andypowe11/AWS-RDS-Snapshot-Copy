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
encryption keys and instance & RDS snapshots in a second 'failsafe' account to which there is limited
and carefully controlled access. Such control could be maintained by splitting the password and the MFS device across
multiple members of staff, requiring two to be present for any access to be possible.

The Lambda functions provided here provide a way of taking a daily copy of the automated snapshots from
one or more RDS databases from a Live account to a Failsafe account.
## Overview
Two Lambda python functions are provided.

The first, rdscopysnappshots.py, runs in the Live account on a daily
basis. It deletes any snapshot copies left over from the previous day's run, creates a new manual copy
of the most recent snapshot for each RDS database, shares it with the Failsafe account and sends an SNS alert
to indicate that the snapshot is available.

The second function, rdssavesnapshot.py, runs in the Failsafe account and is triggered on receipt of the SNS alert.
It takes a manual copy of the newly shared snapshot and deletes any existing snapshots that are older
than a set age.
## Configuration
The following variables should be configured before use:
### rdscopysnapshot.py
### rdssavesnapshot.py
## Usage
Note on timeouts
## Encryption
## Inspiration
Much of the initial thinking for these functions came from my ex-colleague (now working for AWS)
Matt Johnson (mhj@amazon.com),

The functions themselves are partly based on the function at https://github.com/xombiemp/rds-copy-snapshots-lambda.
