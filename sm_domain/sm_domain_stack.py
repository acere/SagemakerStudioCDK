from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
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

        # ToDo make the role a parameter?
        sm_user_policy = iam.ManagedPolicy(
            self,
            "SageMakerDefaultUserPolicy",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:ListBucket",
                    ],
                    resources=["arn:aws:s3:::*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iam:GetRole",
                        "iam:GetRolePolicy",
                    ],
                    resources=["*"],
                ),
            ],
        )
        managed_policies_list = [
            iam.ManagedPolicy.from_aws_managed_policy_name(k)
            for k in [
                "AmazonSageMakerFullAccess",
            ]
        ]

        ### Default role assumed by users defined in this domain
        role = iam.Role(
            self,
            "SageMakerStudioDefaultRole",
            # path="/service-role/",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=managed_policies_list + [sm_user_policy],
        )

        default_user_settings = sagemaker.CfnDomain.UserSettingsProperty(
            execution_role=role.role_arn
        )

        # If no vpc is passed as argument, the stack is deployed in the account default VPC
        # this option requires defining the CDK environment, and doesn't translate cleanly
        # into a CF template
        if vpc is None:
            vpc = ec2.Vpc.from_lookup(self, "vpc", is_default=True)

        # Create a Studio Domain in the defined VPC
        studio_domain = sagemaker.CfnDomain(
            self,
            "StudioDomain",
            auth_mode="IAM",
            default_user_settings=default_user_settings,
            domain_name=domain_name.value_as_string,
            subnet_ids=[k.subnet_id for k in vpc.public_subnets],
            vpc_id=vpc.vpc_id,
        )
        studio_domain.apply_removal_policy(cdk.RemovalPolicy.DESTROY)
        domain_id = studio_domain.ref

        #### Enable Projects for all studio users
        lambda_policy_sc = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "servicecatalog:AcceptPortfolioShare",
                "servicecatalog:ListAcceptedPortfolioShares",
                "servicecatalog:AssociatePrincipalWithPortfolio",
            ],
            resources=["*"],
        )
        lambda_policy_iam = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "iam:GetRole",
            ],
            resources=[role.role_arn],
        )
        lambda_policy_sm = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "sagemaker:EnableSagemakerServicecatalogPortfolio",
                "sagemaker:DisableSagemakerServicecatalogPortfolio",
            ],
            resources=["*"],
        )

        # read the code of the python function to pass it inline to create the lambda fn
        with open("enable_projects_fn/enable_projects.py", encoding="utf8") as fp:
            handler_code = fp.read()

        lambda_fn = lambda_.Function(
            self,
            "LambdaEnableSagemakerProjects",
            code=lambda_.Code.from_inline(handler_code),
            handler="index.lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_8,
            timeout=cdk.Duration.seconds(5),
            initial_policy=[
                lambda_policy_iam,
                lambda_policy_sc,
                lambda_policy_sm,
            ],
        )
        cdk.CustomResource(
            self,
            "CREnableSagemakerProjects",
            service_token=lambda_fn.function_arn,
            properties={"ExecutionRole": role.role_arn},
        )

        ### Define Stack outputs and corresponding exports
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
            value=studio_domain.attr_url,
            description="SageMaker Studio Domain URL",
        )
        cdk.CfnOutput(
            self,
            "EfsFileSystemID",
            value=studio_domain.attr_home_efs_file_system_id,
            description="SageMaker Studio EFS fileSystem ID",
            export_name="StudioDomainEfsId",
        )
        cdk.CfnOutput(
            self,
            "SageMakerStudioUserRole",
            value=role.role_arn,
            description="SageMaker Studio Role ARN",
            export_name="SageMakerStudioUserRole",
        )


        self.vpc = vpc
        self.domain = studio_domain
        self.user_role = role
