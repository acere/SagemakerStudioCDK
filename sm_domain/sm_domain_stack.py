from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sagemaker as sagemaker
from aws_cdk import core as cdk


class SMSDomainStack(cdk.Stack):
    def __init__(
        self, scope: cdk.Construct, construct_id: str, vpc: ec2.Vpc = None, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        domain_name = cdk.CfnParameter(
            self,
            "SMSDomainName",
            type="String",
            description="Domain name",
            default="StudioDomain",
        )

        # ToDo make the roles a parameter
        self.role = iam.Role(
            self,
            "SMStudioRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerFullAccess"
                )
            ],
        )

        default_user_settings = sagemaker.CfnDomain.UserSettingsProperty(
            execution_role=self.role.role_arn
        )

        # If no vpc is passed as argument, the stack is deployed in the account default VPC
        # this optios requires defining the CDK environment, and doesn't translate cleanly
        # into a CF template
        if vpc is None:
            vpc = ec2.Vpc.from_lookup(self, "vpc", is_default=True)

        self.vpc = vpc

        # Create a Studio Domain in the defined VPC
        self.studio_domain = sagemaker.CfnDomain(
            self,
            "StudioDomain",
            auth_mode="IAM",
            default_user_settings=default_user_settings,
            domain_name=domain_name.value_as_string,
            subnet_ids=[k.subnet_id for k in vpc.public_subnets],
            vpc_id=vpc.vpc_id,
        )
        self.studio_domain.apply_removal_policy(cdk.RemovalPolicy.DESTROY)
        domain_id = self.studio_domain.ref

        # Define Stack outputs and corresponding exports
        cdk.CfnOutput(
            self,
            "DomainID",
            value=domain_id,
            description="SageMaker Studio Domain ID",
            export_name="StudioDomainId",
        )
        cdk.CfnOutput(
            self,
            "StudioDomainURL",
            value=self.studio_domain.attr_url,
            description="SageMaker Studio Domain URL",
        )
        cdk.CfnOutput(
            self,
            "EfsFileSystemID",
            value=self.studio_domain.attr_home_efs_file_system_id,
            description="SageMaker Studio EFS fileSystem ID",
            export_name="StudioDomainEfsId",
        )
