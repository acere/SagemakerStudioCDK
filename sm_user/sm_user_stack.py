from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sagemaker as sagemaker
from aws_cdk import core as cdk


class SMSIAMUserStack(cdk.Stack):
    def __init__(
        self,
        scope: cdk.Construct,
        construct_id: str,
        domain: sagemaker.CfnDomain = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

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
        user_name = cdk.CfnParameter(
            self,
            "SMSUserName",
            type="String",
            description="User Name",
            default="StudioUser",
        )

        # Read the StudioDomainId exported by the StudioDomain stack
        StudioDomainId = cdk.Fn.import_value("StudioDomainId")

        user_settings = sagemaker.CfnUserProfile.UserSettingsProperty(
            execution_role=self.role.role_arn
        )
        self.user = sagemaker.CfnUserProfile(
            self,
            "user",
            domain_id=StudioDomainId,
            # single_sign_on_user_identifier="UserName",
            # single_sign_on_user_value="SSOUserName",
            user_profile_name=user_name.value_as_string,
            user_settings=user_settings,
        )
        user_id = self.user.user_profile_name

        if domain is not None:
            self.user.add_depends_on(domain)

        cdk.CfnOutput(
            self,
            "UserID",
            value=user_id,
            description="SageMaker Studio User ID",
            export_name="StudioUserId",
        )

        self.JupyterApp = sagemaker.CfnApp(
            self,
            "StudioApp",
            app_name="defaultApp",
            app_type="JupyterServer",
            domain_id=StudioDomainId,
            user_profile_name=user_id,
        )
        self.JupyterApp.add_depends_on(self.user)
