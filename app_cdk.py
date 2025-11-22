#!/usr/bin/env python3
"Build the VPC, IAM, and VPC resources used to host the travel app"
from aws_cdk import (
    CfnOutput,
    Tags,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_bedrock as bedrock,
    aws_dynamodb as dynamodb,
)
import aws_cdk as cdk

app = cdk.App()
stack = cdk.Stack(app, "TravelAppInfrastructure")

# Create a VPC with a single public subnet
vpc = ec2.Vpc(
    stack,
    "MyVpc",
    ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
    max_azs=1,  # Use one availability zone
    subnet_configuration=[
        ec2.SubnetConfiguration(name="PublicSubnet", subnet_type=ec2.SubnetType.PUBLIC)
    ],
)

# Create role for the web server instance
instance_role = iam.Role(
    stack,
    "InstanceRole",
    assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
    role_name="app-role",
    managed_policies=[
        iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
    ],
)

# Reference the existing role directly from the account
# account_id = os.environ.get("CDK_DEFAULT_ACCOUNT")
# region = os.environ.get("CDK_DEFAULT_REGION")
# existing_role_arn = f"arn:aws:iam::{account_id}:role/app-role"
# existing_role = iam.Role.from_role_arn(
#    stack, "ExistingRole", role_arn=existing_role_arn
# )


# Find the arn for the foundation model
model_arn = bedrock.FoundationModel.from_foundation_model_id(
    stack, "Model", bedrock.FoundationModelIdentifier.AMAZON_NOVA_LITE_V1_0
).model_arn

# Add bedrock permissions to the role
instance_role.add_to_policy(
    iam.PolicyStatement(
        actions=[
            "bedrock:InvokeModelWithResponseStream",
            "bedrock:InvokeModel",
            "bedrock:Retrieve",
            "bedrock:RetrieveAndGenerate",
            "bedrock:ListKnowledgeBases",
        ],
        resources=["arn:aws:bedrock:*:*:*", model_arn],
    )
)

# Find the Cities DynamoDB table
table = dynamodb.Table.from_table_name(stack, id="Cities table", table_name="Cities")

# Add DynamoDB permissions to the role
instance_role.add_to_policy(
    iam.PolicyStatement(
        actions=["dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"],
        resources=[table.table_arn],
    )
)

# Add s3 permissions for codedeploy can access deployment artifacts
instance_role.add_to_policy(
    iam.PolicyStatement(
        actions=["s3:GetObject"], resources=["arn:aws:s3:::codepipeline-*"]
    )
)

# Create the Web Server instance
instance = ec2.Instance(
    stack,
    "WebServer",
    instance_type=ec2.InstanceType.of(
        ec2.InstanceClass.BURSTABLE2, ec2.InstanceSize.MICRO
    ),
    machine_image=ec2.MachineImage.latest_amazon_linux2023(),
    vpc=vpc,
    role=instance_role,
)
# Add the tag we use to deploy from CodeDeploy
Tags.of(instance).add("Name", "travel-app")

# Configure nginx and the CodeDeploy agent
instance.add_user_data(
    "yum install -y nginx ruby",
    "systemctl enable nginx --now",
    "cd ~",
    "wget https://aws-codedeploy-us-east-2.s3.us-east-2.amazonaws.com/latest/install",
    "chmod +x ./install",
    "sudo ./install auto",
)

# Allow security group access from port 80
instance.connections.allow_from_any_ipv4(ec2.Port.tcp(80))

# Add a CfnOutput for the HTTP URL
CfnOutput(stack, "InstanceHttpUrl", value=f"http://{instance.instance_public_ip}")

app.synth()
