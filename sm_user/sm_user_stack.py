from aws_cdk import aws_iam as iam
from aws_cdk import aws_sagemaker as sagemaker
from aws_cdk import core as cdk
from sm_domain.sm_domain_stack import SMSDomainStack



class SMSIAMUserStack(cdk.Stack):
    def __init__(
        self,
        scope: cdk.Construct,
        construct_id: str,
        # domain: SMSDomainStack,
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

        # Read the StudioDomainId exported by the StudioDomain stack
        StudioDomainId = cdk.Fn.import_value("StudioDomainId")
        role_arn = cdk.Fn.import_value("SageMakerStudioUserRole")

        user_settings = sagemaker.CfnUserProfile.UserSettingsProperty(
            execution_role=role_arn
        )
        user = sagemaker.CfnUserProfile(
            self,
            "user",
            domain_id=StudioDomainId,
            # single_sign_on_user_identifier="UserName",
            # single_sign_on_user_value="SSOUserName",
            user_profile_name=user_name.value_as_string,
            user_settings=user_settings,
        )
        user_id = user.user_profile_name

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
                "StudioUserName": user.user_profile_name,
                "DomainID": StudioDomainId,
                "GitRepository": git_repository,
            },
        )
        cr_users_init.node.add_dependency(user)

        self.JupyterApp = sagemaker.CfnApp(
            self,
            "DefaultStudioApp",
            app_name="default",
            app_type="JupyterServer",
            domain_id=StudioDomainId,
            user_profile_name=user_id,
        )
        self.JupyterApp.add_depends_on(user)
