import boto3
from datetime import datetime

ec2 = boto3.client("ec2")

# Define your instance groups manually
dev_instances = [
    "i-0304c8ad0d646a745",  # example dev instance ID
    # "dev-ec2",  # or Name tag
]

prod_instances = [
    # "i-0123abcd4567efgh8",  # example prod instance ID
    # "prod-instance-name-1",  # or Name tag
]

def get_instance_ids_by_name_or_id(names_or_ids):
    """
    Resolves instance names or IDs to actual instance IDs.
    """
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
    """
    Create an AMI for the given instance ID and environment.
    """
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