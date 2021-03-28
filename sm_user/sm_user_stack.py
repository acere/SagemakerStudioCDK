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

        user_name = cdk.CfnParameter(
            self,
            "SMSUserName",
            type="String",
            description="User Name",
            default="StudioUser",
        )

        git_repository = cdk.CfnParameter(
            self,
            "GitRepository",
            type="String",
            description="Git Repository",
            default="https://github.com/acere/SagemakerStudioCDK.git",
        )

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

        provider_service_token = cdk.Fn.import_value("StudioUserProviderToken")
        cr_users_init = cdk.CustomResource(
            self,
            "PopulateUserLambda",
            # service_token=provider.service_token,
            service_token=provider_service_token,
            properties={
                "StudioUserName": self.user.user_profile_name,
                "DomainID": StudioDomainId,
                "GitRepository": git_repository,
            },
        )
        cr_users_init.node.add_dependency(self.user)
        

        self.JupyterApp = sagemaker.CfnApp(
            self,
            "DefaultStudioApp",
            app_name="default",
            app_type="JupyterServer",
            domain_id=StudioDomainId,
            user_profile_name=user_id,
        )
        self.JupyterApp.add_depends_on(self.user)
