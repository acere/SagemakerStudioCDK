# Function: CFEnableSagemakerProjects
# Purpose:  Enables Sagemaker Projects
import json
import boto3
import cfnresponse
client = boto3.client('sagemaker')
sc_client = boto3.client('servicecatalog')
def lambda_handler(event, context):
    response_status = cfnresponse.SUCCESS
    execution_role = event['ResourceProperties']['ExecutionRole']
    
    if 'RequestType' in event and event['RequestType'] == 'Create':
        enable_projects(execution_role)
    cfnresponse.send(event, context, response_status, {}, '')
    if 'RequestType' in event and event['RequestType'] == 'Delete':
        disable_projects(execution_role)
    cfnresponse.send(event, context, response_status, {}, '')


def enable_projects(studio_role_arn):
    # enable Project on account level (accepts portfolio share)
    response = client.enable_sagemaker_servicecatalog_portfolio()
    # associate studio role with portfolio
    response = sc_client.list_accepted_portfolio_shares()
    portfolio_id = ''
    for portfolio in response['PortfolioDetails']:
        if portfolio['ProviderName'] == 'Amazon SageMaker':
            portfolio_id = portfolio['Id']
    response = sc_client.associate_principal_with_portfolio(
        PortfolioId=portfolio_id,
        PrincipalARN=studio_role_arn,
        PrincipalType='IAM'
    )

def disable_projects(studio_role_arn):
    # disable Project on account level (accepts portfolio share)
    response = client.disable_sagemaker_servicecatalog_portfolio()
    # dis-associate studio role with portfolio
    response = sc_client.list_accepted_portfolio_shares()
    portfolio_id = ''
    for portfolio in response['PortfolioDetails']:
        if portfolio['ProviderName'] == 'Amazon SageMaker':
            portfolio_id = portfolio['Id']
    response = sc_client.disassociate_principal_with_portfolio(
        PortfolioId=portfolio_id,
        PrincipalARN=studio_role_arn,
        PrincipalType='IAM'
    )