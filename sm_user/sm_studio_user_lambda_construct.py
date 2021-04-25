from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_efs as efs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python

# from aws_cdk import aws_logs as logs
from aws_cdk import aws_sagemaker as sagemaker
from aws_cdk import core as cdk
from aws_cdk import custom_resources as cr


class StudioUserLambda(cdk.Stack):
    def __init__(
        self,
        scope: cdk.Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        domain: sagemaker.CfnDomain,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        studio_domain_id = (
            domain.attr_domain_id
        )  # cdk.Fn.import_value("StudioDomainId")

        # Get the security group associated with the EFS volume managed by SageMaker Studio
        get_parameter = cr.AwsCustomResource(
            self,
            "GetEfsSgId",
            on_update={  # will also be called for a CREATE event
                "service": "EC2",
                "action": "describeSecurityGroups",
                "parameters": {
                    "Filters": [
                        {"Name": "vpc-id", "Values": [vpc.vpc_id]},
                        {
                            "Name": "group-name",
                            "Values": [
                                f"security-group-for-inbound-nfs-{studio_domain_id}"
                            ],
                        },
                    ]
                },
                "physical_resource_id": cr.PhysicalResourceId.of("GetEfsSgId"),
            },
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            ),
        )
        sg_name = get_parameter.get_response_field("SecurityGroups.0.GroupId")
        sg_efs = ec2.SecurityGroup.from_security_group_id(
            self, "SG", security_group_id=sg_name
        )

        # We can now retrive a handler for the EFS volume
        StudioDomainEfsId = cdk.Fn.import_value("StudioDomainEfsId")
        studio_efs = efs.FileSystem.from_file_system_attributes(
            self, "StudioEFS", file_system_id=StudioDomainEfsId, security_group=sg_efs
        )

        # Create EFS access point to enable the lambda fn to mount the EFS volume
        efs_ap = efs.AccessPoint(
            self,
            "EfsAccessPoint",
            file_system=studio_efs,
            posix_user=efs.PosixUser(gid="0", uid="0"),
        )

        # Function that takes care of setting up the user environment
        self.lambda_fn = lambda_python.PythonFunction(
            self,
            "UserSetupLambdaFn",
            entry="populate_git_fn",
            index="populate_from_git.py",
            handler="on_event",
            vpc=vpc,
            layers=[
                lambda_.LayerVersion.from_layer_version_arn(
                    self,
                    "GitLayer",
                    layer_version_arn=f"arn:aws:lambda:{self.region}:553035198032:layer:git-lambda2:8",
                ),
            ],
            filesystem=lambda_.FileSystem.from_efs_access_point(efs_ap, "/mnt/efs"),
            timeout=cdk.Duration.seconds(300),
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "sagemaker:DescribeUserProfile",
                    ],
                    resources=["*"],
                )
            ],
        )

        provider = cr.Provider(
            self,
            "Provider",
            on_event_handler=self.lambda_fn,
        )

        cdk.CfnOutput(
            self,
            "StudioUserProviderToken",
            value=provider.service_token,
            description="StudioUserProviderToken",
            export_name="StudioUserProviderToken",
        )

        self.provider = provider
