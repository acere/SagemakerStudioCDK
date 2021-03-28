#!/usr/bin/env python3
from aws_cdk import core as cdk

from sm_domain.sm_domain_stack import SMSDomainStack
from sm_domain.vpc_construct import VpcStack
from sm_user.service_catalog_construct import ServiceCatalogStudioUserStack

# To use the default VPC, it is necessary to define the environment.
# from dotenv import find_dotenv, load_dotenv
# load_dotenv(find_dotenv())
#
# env = cdk.Environment(
#     region=os.getenv("CDK_DEPLOY_REGION"), account=os.getenv("CDK_DEPLOY_ACCOUNT")
# )

app = cdk.App()

vpc = VpcStack(
    app,
    "SageMakerStudioVpc",
    # env=env
)
studio_domain = SMSDomainStack(
    app,
    "SageMakerStudioDomain",
    vpc=vpc.vpc,
    # env=env
)
studio_user_sc = ServiceCatalogStudioUserStack(
    app,
    "ServiceCatalogStudioUserStack",
    domain=studio_domain,
    # env=env
)

app.synth()
