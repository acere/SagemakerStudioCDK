from aws_cdk import aws_s3_assets as s3assets
from aws_cdk import aws_servicecatalog as servicecatalog
from aws_cdk import core as cdk
from aws_cdk import aws_iam as iam
from sm_user.sm_user_stack import SMSIAMUserStack


class StudioUserStack(cdk.Stack):
    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # We start by generating the CF template for the studio user
        stage = cdk.Stage(self, "DummyStage")
        SMSIAMUserStack(
            stage, "StudioUserStack", synthesizer=cdk.BootstraplessSynthesizer()
        )
        assembly = stage.synth(force=True)

        # Retrive the local path of the CF template
        template_full_path = assembly.stacks[0].template_full_path

        # Upload CF template to s3 to create an asset to reference
        s3_asset = s3assets.Asset(
            self,
            "TemplateAsset",
            path=template_full_path,
        )

        # Create the Service Catalog product referencing the CF template
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

        # Create the Porduct Portfolio
        sc_portfolio = servicecatalog.CfnPortfolio(
            self,
            "SageMakerPortfolio",
            display_name="SageMakerPortfolio",
            provider_name="SageMakerTemplate",
        )

        # Associate the Studio User to the Portfolio
        servicecatalog.CfnPortfolioProductAssociation(
            self,
            "ProductAssociation",
            portfolio_id=sc_portfolio.ref,
            product_id=sc_product.ref,
        )

        sc_group = iam.Group(
            self,
            "StudioUserGroup",
            group_name="SageMakerStudioUserGroup",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSServiceCatalogEndUserReadOnlyAccess"
                )
            ],
        )

        # Associate a role
        servicecatalog.CfnPortfolioPrincipalAssociation(
            self,
            "PortfolioPrincipalAssociacion",
            portfolio_id=sc_portfolio.ref,
            principal_arn=sc_group.group_arn,
            principal_type="IAM",
        )
