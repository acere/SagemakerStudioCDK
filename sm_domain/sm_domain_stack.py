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

        SMSCPL_policy = iam.ManagedPolicy(
            self,
            "AmazonSageMakerAdmin-ServiceCatalogProductsServiceRolePolicy",
            managed_policy_name="AmazonSageMakerAdmin-ServiceCatalogProductsServiceRolePolicy",
            document=iam.PolicyDocument.from_json(
                AmazonSageMakerAdmin_ServiceCatalogProductsServiceRolePolicy
            ),
        )

        SMSCPL_role = iam.Role(
            self,
            "AmazonSageMakerServiceCatalogProductsLaunchRole",
            role_name="AmazonSageMakerServiceCatalogProductsLaunchRole",
            path="/service-role/",
            managed_policies=[SMSCPL_policy],
            assumed_by=iam.ServicePrincipal("servicecatalog.amazonaws.com"),
            description="SageMaker role created from the SageMaker AWS Management Console. This role has the permissions required to launch the Amazon SageMaker portfolio of products from AWS ServiceCatalog.",
        )

        SMSCPU_policy = iam.ManagedPolicy(
            self,
            "AmazonSageMakerServiceCatalogProductsUseRolePolicy",
            managed_policy_name="AmazonSageMakerServiceCatalogProductsUseRolePolicy",
            document=iam.PolicyDocument.from_json(
                AmazonSageMakerServiceCatalogProductsUseRolePolicy
            ),
        )

        SMSCPU_role = iam.Role(
            self,
            "AmazonSageMakerServiceCatalogProductsUseRole",
            role_name="AmazonSageMakerServiceCatalogProductsUseRole",
            path="/service-role/",
            managed_policies=[SMSCPU_policy],
            assumed_by=iam.CompositePrincipal(
                *[
                    iam.ServicePrincipal(k)
                    for k in [
                        "cloudformation.amazonaws.com",
                        "apigateway.amazonaws.com",
                        "lambda.amazonaws.com",
                        "codebuild.amazonaws.com",
                        "sagemaker.amazonaws.com",
                        "glue.amazonaws.com",
                        "events.amazonaws.com",
                        "states.amazonaws.com",
                        "codepipeline.amazonaws.com",
                        "firehose.amazonaws.com",
                    ]
                ]
            ),
            description="SageMaker role created from the SageMaker AWS Management Console. This role has the permissions required to use the Amazon SageMaker portfolio of products from AWS ServiceCatalog.",
        )


AmazonSageMakerAdmin_ServiceCatalogProductsServiceRolePolicy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "apigateway:GET",
                "apigateway:POST",
                "apigateway:PUT",
                "apigateway:PATCH",
                "apigateway:DELETE",
            ],
            "Resource": "*",
            "Condition": {
                "StringLike": {"aws:ResourceTag/sagemaker:launch-source": "*"}
            },
        },
        {
            "Effect": "Allow",
            "Action": ["apigateway:POST"],
            "Resource": "*",
            "Condition": {
                "ForAnyValue:StringLike": {"aws:TagKeys": ["sagemaker:launch-source"]}
            },
        },
        {
            "Effect": "Allow",
            "Action": ["apigateway:PATCH"],
            "Resource": ["arn:aws:apigateway:*::/account"],
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudformation:CreateStack",
                "cloudformation:UpdateStack",
                "cloudformation:DeleteStack",
            ],
            "Resource": "arn:aws:cloudformation:*:*:stack/SC-*",
            "Condition": {
                "ArnLikeIfExists": {
                    "cloudformation:RoleArn": [
                        "arn:aws:sts::*:assumed-role/AmazonSageMakerServiceCatalog*"
                    ]
                }
            },
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudformation:DescribeStackEvents",
                "cloudformation:DescribeStacks",
            ],
            "Resource": "arn:aws:cloudformation:*:*:stack/SC-*",
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudformation:GetTemplateSummary",
                "cloudformation:ValidateTemplate",
            ],
            "Resource": "*",
        },
        {
            "Effect": "Allow",
            "Action": [
                "codebuild:CreateProject",
                "codebuild:DeleteProject",
                "codebuild:UpdateProject",
            ],
            "Resource": ["arn:aws:codebuild:*:*:project/sagemaker-*"],
        },
        {
            "Effect": "Allow",
            "Action": [
                "codecommit:CreateCommit",
                "codecommit:CreateRepository",
                "codecommit:DeleteRepository",
                "codecommit:GetRepository",
                "codecommit:TagResource",
            ],
            "Resource": ["arn:aws:codecommit:*:*:sagemaker-*"],
        },
        {"Effect": "Allow", "Action": ["codecommit:ListRepositories"], "Resource": "*"},
        {
            "Effect": "Allow",
            "Action": [
                "codepipeline:CreatePipeline",
                "codepipeline:DeletePipeline",
                "codepipeline:GetPipeline",
                "codepipeline:GetPipelineState",
                "codepipeline:StartPipelineExecution",
                "codepipeline:TagResource",
                "codepipeline:UpdatePipeline",
            ],
            "Resource": ["arn:aws:codepipeline:*:*:sagemaker-*"],
        },
        {
            "Effect": "Allow",
            "Action": ["cognito-idp:CreateUserPool"],
            "Resource": "*",
            "Condition": {
                "ForAnyValue:StringLike": {"aws:TagKeys": ["sagemaker:launch-source"]}
            },
        },
        {
            "Effect": "Allow",
            "Action": [
                "cognito-idp:CreateGroup",
                "cognito-idp:CreateUserPoolDomain",
                "cognito-idp:CreateUserPoolClient",
                "cognito-idp:DeleteGroup",
                "cognito-idp:DeleteUserPool",
                "cognito-idp:DeleteUserPoolClient",
                "cognito-idp:DeleteUserPoolDomain",
                "cognito-idp:DescribeUserPool",
                "cognito-idp:DescribeUserPoolClient",
                "cognito-idp:UpdateUserPool",
                "cognito-idp:UpdateUserPoolClient",
            ],
            "Resource": "*",
            "Condition": {
                "StringLike": {"aws:ResourceTag/sagemaker:launch-source": "*"}
            },
        },
        {
            "Action": ["ecr:CreateRepository", "ecr:DeleteRepository"],
            "Resource": ["arn:aws:ecr:*:*:repository/sagemaker-*"],
            "Effect": "Allow",
        },
        {
            "Effect": "Allow",
            "Action": [
                "events:DescribeRule",
                "events:DeleteRule",
                "events:DisableRule",
                "events:EnableRule",
                "events:PutRule",
                "events:PutTargets",
                "events:RemoveTargets",
            ],
            "Resource": ["arn:aws:events:*:*:rule/sagemaker-*"],
        },
        {
            "Effect": "Allow",
            "Action": [
                "firehose:CreateDeliveryStream",
                "firehose:DeleteDeliveryStream",
                "firehose:DescribeDeliveryStream",
                "firehose:StartDeliveryStreamEncryption",
                "firehose:StopDeliveryStreamEncryption",
                "firehose:UpdateDestination",
            ],
            "Resource": "arn:aws:firehose:*:*:deliverystream/sagemaker-*",
        },
        {
            "Action": ["glue:CreateDatabase", "glue:DeleteDatabase"],
            "Resource": [
                "arn:aws:glue:*:*:catalog",
                "arn:aws:glue:*:*:database/sagemaker-*",
                "arn:aws:glue:*:*:table/sagemaker-*",
                "arn:aws:glue:*:*:userDefinedFunction/sagemaker-*",
            ],
            "Effect": "Allow",
        },
        {
            "Action": [
                "glue:CreateClassifier",
                "glue:DeleteClassifier",
                "glue:DeleteCrawler",
                "glue:DeleteJob",
                "glue:DeleteTrigger",
                "glue:DeleteWorkflow",
                "glue:StopCrawler",
            ],
            "Resource": ["*"],
            "Effect": "Allow",
        },
        {
            "Action": ["glue:CreateWorkflow"],
            "Resource": ["arn:aws:glue:*:*:workflow/sagemaker-*"],
            "Effect": "Allow",
        },
        {
            "Action": ["glue:CreateJob"],
            "Resource": ["arn:aws:glue:*:*:job/sagemaker-*"],
            "Effect": "Allow",
        },
        {
            "Action": ["glue:CreateCrawler", "glue:GetCrawler"],
            "Resource": ["arn:aws:glue:*:*:crawler/sagemaker-*"],
            "Effect": "Allow",
        },
        {
            "Action": ["glue:CreateTrigger", "glue:GetTrigger"],
            "Resource": ["arn:aws:glue:*:*:trigger/sagemaker-*"],
            "Effect": "Allow",
        },
        {
            "Effect": "Allow",
            "Action": ["iam:PassRole"],
            "Resource": [
                "arn:aws:iam::*:role/service-role/AmazonSageMakerServiceCatalog*"
            ],
        },
        {
            "Effect": "Allow",
            "Action": [
                "lambda:AddPermission",
                "lambda:CreateFunction",
                "lambda:DeleteFunction",
                "lambda:GetFunction",
                "lambda:GetFunctionConfiguration",
                "lambda:InvokeFunction",
                "lambda:RemovePermission",
            ],
            "Resource": ["arn:aws:lambda:*:*:function:sagemaker-*"],
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:DeleteLogGroup",
                "logs:DeleteLogStream",
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams",
                "logs:PutRetentionPolicy",
            ],
            "Resource": [
                "arn:aws:logs:*:*:log-group:/aws/apigateway/AccessLogs/*",
                "arn:aws:logs:*:*:log-group::log-stream:*",
            ],
        },
        {
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": "*",
            "Condition": {
                "StringEquals": {
                    "s3:ExistingObjectTag/servicecatalog:provisioning": "true"
                }
            },
        },
        {
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": ["arn:aws:s3:::sagemaker-*"],
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:DeleteBucket",
                "s3:DeleteBucketPolicy",
                "s3:GetBucketPolicy",
                "s3:PutBucketAcl",
                "s3:PutBucketNotification",
                "s3:PutBucketPolicy",
                "s3:PutBucketPublicAccessBlock",
                "s3:PutBucketLogging",
                "s3:PutEncryptionConfiguration",
            ],
            "Resource": "arn:aws:s3:::sagemaker-*",
        },
        {
            "Action": [
                "sagemaker:CreateEndpoint",
                "sagemaker:CreateEndpointConfig",
                "sagemaker:CreateModel",
                "sagemaker:CreateWorkteam",
                "sagemaker:DeleteEndpoint",
                "sagemaker:DeleteEndpointConfig",
                "sagemaker:DeleteModel",
                "sagemaker:DeleteWorkteam",
                "sagemaker:DescribeModel",
                "sagemaker:DescribeEndpointConfig",
                "sagemaker:DescribeEndpoint",
                "sagemaker:DescribeWorkteam",
            ],
            "Resource": ["arn:aws:sagemaker:*:*:*"],
            "Effect": "Allow",
        },
        {
            "Action": [
                "states:CreateStateMachine",
                "states:DeleteStateMachine",
                "states:UpdateStateMachine",
            ],
            "Resource": ["arn:aws:states:*:*:stateMachine:sagemaker-*"],
            "Effect": "Allow",
        },
    ],
}

AmazonSageMakerServiceCatalogProductsUseRolePolicy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
                "cloudformation:CreateChangeSet",
                "cloudformation:CreateStack",
                "cloudformation:DescribeChangeSet",
                "cloudformation:DeleteChangeSet",
                "cloudformation:DeleteStack",
                "cloudformation:DescribeStacks",
                "cloudformation:ExecuteChangeSet",
                "cloudformation:SetStackPolicy",
                "cloudformation:UpdateStack",
            ],
            "Resource": "arn:aws:cloudformation:*:*:stack/sagemaker-*",
            "Effect": "Allow",
        },
        {"Action": ["cloudwatch:PutMetricData"], "Resource": "*", "Effect": "Allow"},
        {
            "Action": ["codebuild:BatchGetBuilds", "codebuild:StartBuild"],
            "Resource": [
                "arn:aws:codebuild:*:*:project/sagemaker-*",
                "arn:aws:codebuild:*:*:build/sagemaker-*",
            ],
            "Effect": "Allow",
        },
        {
            "Action": [
                "codecommit:CancelUploadArchive",
                "codecommit:GetBranch",
                "codecommit:GetCommit",
                "codecommit:GetUploadArchiveStatus",
                "codecommit:UploadArchive",
            ],
            "Resource": "arn:aws:codecommit:*:*:sagemaker-*",
            "Effect": "Allow",
        },
        {
            "Action": ["codepipeline:StartPipelineExecution"],
            "Resource": "arn:aws:codepipeline:*:*:sagemaker-*",
            "Effect": "Allow",
        },
        {"Action": ["ec2:DescribeRouteTables"], "Resource": "*", "Effect": "Allow"},
        {
            "Action": [
                "ecr:BatchCheckLayerAvailability",
                "ecr:BatchGetImage",
                "ecr:Describe*",
                "ecr:GetAuthorizationToken",
                "ecr:GetDownloadUrlForLayer",
            ],
            "Resource": "*",
            "Effect": "Allow",
        },
        {
            "Effect": "Allow",
            "Action": [
                "ecr:BatchDeleteImage",
                "ecr:CompleteLayerUpload",
                "ecr:CreateRepository",
                "ecr:DeleteRepository",
                "ecr:InitiateLayerUpload",
                "ecr:PutImage",
                "ecr:UploadLayerPart",
            ],
            "Resource": ["arn:aws:ecr:*:*:repository/sagemaker-*"],
        },
        {
            "Action": [
                "events:DeleteRule",
                "events:DescribeRule",
                "events:PutRule",
                "events:PutTargets",
                "events:RemoveTargets",
            ],
            "Resource": ["arn:aws:events:*:*:rule/sagemaker-*"],
            "Effect": "Allow",
        },
        {
            "Action": ["firehose:PutRecord", "firehose:PutRecordBatch"],
            "Resource": "arn:aws:firehose:*:*:deliverystream/sagemaker-*",
            "Effect": "Allow",
        },
        {
            "Action": [
                "glue:BatchCreatePartition",
                "glue:BatchDeletePartition",
                "glue:BatchDeleteTable",
                "glue:BatchDeleteTableVersion",
                "glue:BatchGetPartition",
                "glue:CreateDatabase",
                "glue:CreatePartition",
                "glue:CreateTable",
                "glue:DeletePartition",
                "glue:DeleteTable",
                "glue:DeleteTableVersion",
                "glue:GetDatabase",
                "glue:GetPartition",
                "glue:GetPartitions",
                "glue:GetTable",
                "glue:GetTables",
                "glue:GetTableVersion",
                "glue:GetTableVersions",
                "glue:SearchTables",
                "glue:UpdatePartition",
                "glue:UpdateTable",
            ],
            "Resource": [
                "arn:aws:glue:*:*:catalog",
                "arn:aws:glue:*:*:database/default",
                "arn:aws:glue:*:*:database/global_temp",
                "arn:aws:glue:*:*:database/sagemaker-*",
                "arn:aws:glue:*:*:table/sagemaker-*",
                "arn:aws:glue:*:*:tableVersion/sagemaker-*",
            ],
            "Effect": "Allow",
        },
        {
            "Action": ["iam:PassRole"],
            "Resource": [
                "arn:aws:iam::*:role/service-role/AmazonSageMakerServiceCatalogProductsUse*"
            ],
            "Effect": "Allow",
        },
        {
            "Effect": "Allow",
            "Action": ["lambda:InvokeFunction"],
            "Resource": ["arn:aws:lambda:*:*:function:sagemaker-*"],
        },
        {
            "Action": [
                "logs:CreateLogDelivery",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:DeleteLogDelivery",
                "logs:Describe*",
                "logs:GetLogDelivery",
                "logs:GetLogEvents",
                "logs:ListLogDeliveries",
                "logs:PutLogEvents",
                "logs:PutResourcePolicy",
                "logs:UpdateLogDelivery",
            ],
            "Resource": "*",
            "Effect": "Allow",
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:DeleteBucket",
                "s3:GetBucketAcl",
                "s3:GetBucketCors",
                "s3:GetBucketLocation",
                "s3:ListAllMyBuckets",
                "s3:ListBucket",
                "s3:ListBucketMultipartUploads",
                "s3:PutBucketCors",
            ],
            "Resource": ["arn:aws:s3:::aws-glue-*", "arn:aws:s3:::sagemaker-*"],
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:AbortMultipartUpload",
                "s3:DeleteObject",
                "s3:GetObject",
                "s3:GetObjectVersion",
                "s3:PutObject",
            ],
            "Resource": ["arn:aws:s3:::aws-glue-*", "arn:aws:s3:::sagemaker-*"],
        },
        {
            "Effect": "Allow",
            "Action": ["sagemaker:*"],
            "NotResource": [
                "arn:aws:sagemaker:*:*:domain/*",
                "arn:aws:sagemaker:*:*:user-profile/*",
                "arn:aws:sagemaker:*:*:app/*",
                "arn:aws:sagemaker:*:*:flow-definition/*",
            ],
        },
        {
            "Action": [
                "states:DescribeExecution",
                "states:DescribeStateMachine",
                "states:DescribeStateMachineForExecution",
                "states:GetExecutionHistory",
                "states:ListExecutions",
                "states:ListTagsForResource",
                "states:StartExecution",
                "states:StopExecution",
                "states:TagResource",
                "states:UntagResource",
                "states:UpdateStateMachine",
            ],
            "Resource": [
                "arn:aws:states:*:*:stateMachine:sagemaker-*",
                "arn:aws:states:*:*:execution:sagemaker-*:*",
            ],
            "Effect": "Allow",
        },
        {"Action": ["states:ListStateMachines"], "Resource": "*", "Effect": "Allow"},
    ],
}