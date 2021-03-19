#!/usr/bin/env python3

import os

from aws_cdk import core as cdk
from dotenv import find_dotenv, load_dotenv

from sm_user.sm_domain_stack import SMSDomainStack
from sm_user.sm_user_stack import SMSIAMUserStack
from sm_user.vpc_construct import VpcStack
from service_catalog.service_catalog_construct import DeploymentStack

load_dotenv(find_dotenv())

env = cdk.Environment(
    region=os.getenv("CDK_DEPLOY_REGION"), account=os.getenv("CDK_DEPLOY_ACCOUNT")
)

app = cdk.App()

vpc = VpcStack(app, "SageMakerStudioVpc", env=env)
domain = SMSDomainStack(app, "SageMakerStudioDomain", vpc=vpc.vpc, env=env)
# user = SMSIAMUserStack(
#     app, construct_id="SageMakerStudioUser", domain=domain.studio_domain
# )
service_catalog_product = DeploymentStack(app, "DeploymentStack")

app.synth()
