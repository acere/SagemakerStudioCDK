from pathlib import Path

from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_assets as s3assets
from aws_cdk import aws_sagemaker as sagemaker
from aws_cdk import aws_servicecatalog as servicecatalog
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


class DeploymentStack(cdk.Stack):
    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stage = cdk.Stage(self, "DummyStage")
        SMSIAMUserStack(stage, "stack", synthesizer=cdk.BootstraplessSynthesizer())

        assembly = stage.synth(force=True)

        template_full_path = assembly.stacks[0].template_full_path
        template_file_name = assembly.stacks[0].template_file

        print(Path(template_full_path))
        print(assembly.stacks[0].template_file)

        s3_asset = s3assets.Asset(
            self,
            "TemplateAsset",
            path=template_full_path,
        )

        sc_product = servicecatalog.CfnCloudFormationProduct(
            self,
            "StudioUser",
            owner="SageMakerStudio",
            provisioning_artifact_parameters=[
                servicecatalog.CfnCloudFormationProduct.ProvisioningArtifactPropertiesProperty(
                    info={"LoadTemplateFromURL": s3_asset.s3_url}
                )
            ],
            name="StudioUser",
        )

        sc_portfolio = servicecatalog.CfnPortfolio(
            self,
            "SageMakerPortfolio",
            display_name="SageMakerPortfolio",
            provider_name="SageMakerTemplate",
        )

        servicecatalog.CfnPortfolioProductAssociation(
            self,
            "ProductAssociation",
            portfolio_id=sc_portfolio.ref,
            product_id=sc_product.ref,
        )

        servicecatalog.CfnPortfolioPrincipalAssociation(
            self,
            "PortfolioPrincipalAssociacion",
            portfolio_id=sc_portfolio.ref,
            principal_arn=f"arn:aws:iam::{self.account}:role/DS00",
            principal_type="IAM",
        )
