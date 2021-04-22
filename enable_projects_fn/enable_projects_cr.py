import boto3
import logging

client = boto3.client('sagemaker')
sc_client = boto3.client('servicecatalog')


def on_event(event, context):
    request_type = event["RequestType"]
    if request_type == "Create":
        return on_create(event)
    if request_type == "Update":
        return on_update(event)
    if request_type == "Delete":
        return on_delete(event)
    raise Exception(f"Invalid request type: {request_type}")

def on_create(event):
    props = event["ResourceProperties"]
    execution_role = props['ExecutionRole']
    response = client.enable_sagemaker_servicecatalog_portfolio()

    # associate studio role with portfolio
    response = sc_client.list_accepted_portfolio_shares()
    portfolio_id = ''
    for portfolio in response['PortfolioDetails']:
        if portfolio['ProviderName'] == 'Amazon SageMaker':
            portfolio_id = portfolio['Id']
    response = sc_client.associate_principal_with_portfolio(
        PortfolioId=portfolio_id,
        PrincipalARN=execution_role,
        PrincipalType='IAM'
    )
def on_delete(event):
    physical_id = event["PhysicalResourceId"]
    props = event["ResourceProperties"]

    logging.info("**Received delete event")
    logging.info(
        f"**Deleting this configuration is a no-op"
    )

def on_update(event):
    physical_id = event["PhysicalResourceId"]
    props = event["ResourceProperties"]
    logging.info("**Received update event")
    logging.info(
        "**Updating this configuration is a no-op",
    )
