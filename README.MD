# AMI Creation and Retention Lambda Scripts

This documentation explains two AWS Lambda scripts using Boto3:
1. **AMI Creation Script**: Automatically creates AMIs for specific EC2 instances.
2. **AMI Retention Script**: Deletes old AMIs created by the above script based on environment type.

---

## 1. AMI Creation Script

This script creates AMIs for a list of EC2 instances based on instance name or instance ID.

### Manual Configuration:
Define your instances manually like below:
```python
# Define your instance groups manually
dev_instances = [
    "i-0304c8ad0d646a745",  # dev instance ID or name
    # "dev-instance-name"
]

prod_instances = [
    # "i-0123abcd4567efgh8",
    # "prod-instance-name"
]
```

### Script Logic:
```python
import boto3
from datetime import datetime

ec2 = boto3.client("ec2")

def get_instance_ids_by_name_or_id(names_or_ids):
    filters = [
        {"Name": "instance-state-name", "Values": ["running", "stopped"]}
    ]
    reservations = ec2.describe_instances(Filters=filters)["Reservations"]

    resolved_ids = []
    for reservation in reservations:
        for instance in reservation["Instances"]:
            instance_id = instance["InstanceId"]
            instance_name = ""
            for tag in instance.get("Tags", []):
                if tag["Key"] == "Name":
                    instance_name = tag["Value"]

            if instance_id in names_or_ids or instance_name in names_or_ids:
                resolved_ids.append(instance_id)

    return resolved_ids

def create_ami(instance_id, env):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
    name = f"{env}-ami-{instance_id}-{timestamp}"

    print(f"Creating AMI for {env.upper()} instance: {instance_id}")
    response = ec2.create_image(
        InstanceId=instance_id,
        Name=name,
        Description=f"Automated AMI for {env.upper()} - {instance_id}",
        NoReboot=True,
        TagSpecifications=[
            {
                "ResourceType": "image",
                "Tags": [
                    {"Key": "Environment", "Value": env},
                    {"Key": "CreatedBy", "Value": "LambdaAutomation"},
                    {"Key": "Name", "Value": name},
                ]
            }
        ]
    )
    print(f"AMI creation started: {response['ImageId']}")

def lambda_handler(event, context):
    dev_ids = get_instance_ids_by_name_or_id(dev_instances)
    prod_ids = get_instance_ids_by_name_or_id(prod_instances)

    for instance_id in dev_ids:
        create_ami(instance_id, "dev")

    for instance_id in prod_ids:
        create_ami(instance_id, "prod")
```

---

## 2. AMI Retention Script

This script deletes AMIs created by the above script if they exceed a specific age.

### Retention Period (in hours):
```python
retention_hours = {
    "dev": 10,   # 10 hours for testing (change to 72 for 3 days)
    "prod": 168  # 7 days
}
```

### Script Logic:
```python
import boto3
from datetime import datetime, timedelta

ec2 = boto3.client("ec2")

retention_hours = {
    "dev": 10,
    "prod": 168
}

def lambda_handler(event, context):
    images = ec2.describe_images(
        Owners=["self"],
        Filters=[
            {"Name": "tag:CreatedBy", "Values": ["LambdaAutomation"]}
        ]
    )["Images"]

    for image in images:
        env_tag = next((tag["Value"] for tag in image.get("Tags", []) if tag["Key"] == "Environment"), None)
        created_time = image["CreationDate"]
        image_id = image["ImageId"]

        if env_tag in retention_hours:
            created_datetime = datetime.strptime(created_time, "%Y-%m-%dT%H:%M:%S.%fZ")
            age_hours = (datetime.utcnow() - created_datetime).total_seconds() / 3600

            if age_hours >= retention_hours[env_tag]:
                print(f"Deregistering AMI: {image_id}, Age: {age_hours:.2f} hours, Env: {env_tag}")
                ec2.deregister_image(ImageId=image_id)

                for mapping in image.get("BlockDeviceMappings", []):
                    if "Ebs" in mapping and "SnapshotId" in mapping["Ebs"]:
                        snapshot_id = mapping["Ebs"]["SnapshotId"]
                        try:
                            ec2.delete_snapshot(SnapshotId=snapshot_id)
                            print(f"Deleted snapshot: {snapshot_id}")
                        except Exception as e:
                            print(f"Error deleting snapshot {snapshot_id}: {str(e)}")
```
┌───────────────────────────────────────────┐
│      Scheduled AMI Creation Process       │
└───────────────────────────────────────────┘
            │
            ▼
 [Triggered by EventBridge at 3:30 AM daily]
            │
            ▼
  [Lambda Function Starts Execution]
            │
            ▼
 [Load EC2 instance names or IDs for dev/prod]
            │
            ▼
 [For each instance (dev/prod):]
            │
            ▼
 [Create AMI with Tags:
   - Environment = dev/prod
   - CreatedBy = LambdaAutomation
   - Name = <env>-ami-<id>-<timestamp>]
            │
            ▼
      [AMI creation complete]

─────────────────────────────────────────────

┌───────────────────────────────────────────┐
│         AMI Retention Process             │
└───────────────────────────────────────────┘
            │
            ▼
 [Triggered by EventBridge daily]
            │
            ▼
 [Lambda fetches AMIs tagged with:
   CreatedBy = LambdaAutomation]
            │
            ▼
 [For each AMI:]
            │
            ▼
 [Check tag: Environment = dev or prod]
            │
            ▼
 [Calculate age of AMI in hours]
            │
            ▼
 [If dev AND age > 10h] OR [If prod AND age > 168h]
            │
            ▼
 [Deregister AMI and delete snapshots]
            │
            ▼
      [Cleanup completed]

---

## 💡 Notes:
- You must tag AMIs with `CreatedBy = LambdaAutomation` and `Environment = dev|prod`.
- Both scripts are Lambda-compatible and should be scheduled using EventBridge (e.g., every day at 3:30 AM).
- Change retention from 10 hours to actual production values after testing (72h = 3 days for dev).

Let me know if you want a zip file or deployment guide!

