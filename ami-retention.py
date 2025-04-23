import boto3
from datetime import datetime, timedelta

ec2 = boto3.client("ec2")

# Retention policy (in hours for testing)
retention_hours = {
    "dev": 10,  # Change to 72 for 3 days
    "prod": 168  # Change to 168 for 7 days
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
                # Deregister AMI
                ec2.deregister_image(ImageId=image_id)

                # Delete associated snapshots
                for mapping in image.get("BlockDeviceMappings", []):
                    if "Ebs" in mapping and "SnapshotId" in mapping["Ebs"]:
                        snapshot_id = mapping["Ebs"]["SnapshotId"]
                        try:
                            ec2.delete_snapshot(SnapshotId=snapshot_id)
                            print(f"Deleted snapshot: {snapshot_id}")
                        except Exception as e:
                            print(f"Error deleting snapshot {snapshot_id}: {str(e)}")
