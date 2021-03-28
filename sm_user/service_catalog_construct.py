from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3_assets as s3assets
from aws_cdk import aws_servicecatalog as servicecatalog
from aws_cdk import core as cdk
from sm_domain.sm_domain_stack import SMSDomainStack

from sm_user.sm_studio_user_lambda_construct import StudioUserLambda
from sm_user.sm_user_stack import SMSIAMUserStack


class ServiceCatalogStudioUserStack(cdk.Stack):
    def __init__(
        self, scope: cdk.Construct, construct_id: str, domain: SMSDomainStack, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create the Lambda Stack for pre-populating the user home directory
        studio_user_lambda = StudioUserLambda(
            self, "FnPopulateStudioUser", vpc=domain.vpc, domain=domain.studio_domain
        )

        # Generate the CF template for the studio user
        stage = cdk.Stage(self, "DummyStage")
        SMSIAMUserStack(
            stage,
            "StudioUserStack",
            synthesizer=cdk.BootstraplessSynthesizer(),
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

        # Associate the Studio User Template to the Portfolio
        servicecatalog.CfnPortfolioProductAssociation(
            self,
            "ProductAssociation",
            portfolio_id=sc_portfolio.ref,
            product_id=sc_product.ref,
        )


        # Associate a role with the portfolio
        sc_role = iam.Role(
            self,
            "StudioAdminRole",
            assumed_by=iam.AnyPrincipal(), 
            role_name="SageMakerStudioAdminRole",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSServiceCatalogEndUserReadOnlyAccess"
                )
            ],
        )

        servicecatalog.CfnPortfolioPrincipalAssociation(
            self,
            "PortfolioPrincipalAssociacion",
            portfolio_id=sc_portfolio.ref,
            principal_arn=sc_role.role_arn,
            principal_type="IAM",
        )
