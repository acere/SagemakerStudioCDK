#!/usr/bin/env python3

import os

from aws_cdk import core as cdk
from dotenv import find_dotenv, load_dotenv

from service_catalog.service_catalog_construct import StudioUserStack
from sm_user.sm_domain_stack import SMSDomainStack
from sm_user.vpc_construct import VpcStack

# load_dotenv(find_dotenv())

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

studio_user_sc = StudioUserStack(app, "ServiceCatalogStudioUserStack")

app.synth()
