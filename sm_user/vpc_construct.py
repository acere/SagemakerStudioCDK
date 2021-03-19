from aws_cdk import aws_ec2 as ec2
from aws_cdk import core


class VpcStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.vpc = ec2.Vpc(
            self,
            "VPC-SageMaker",
            max_azs=1,
            cidr="10.10.0.0/16",
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC, name="Public", cidr_mask=24
                ),
                # ec2.SubnetConfiguration(
                #     subnet_type=ec2.SubnetType.PRIVATE, name="Private", cidr_mask=24
                # )
            ],
            # nat_gateway_provider=ec2.NatProvider.gateway(),
            # nat_gateways=1,
        )

        # Create VPC endpoints for the relevant services
        SageMakerRuntimeEndpoint = self.vpc.add_interface_endpoint(
            "SageMakerRuntimeEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SAGEMAKER_RUNTIME,
        )
        SageMakerRuntimeEndpoint.connections.allow_default_port_from_any_ipv4()
        self.vpc.add_interface_endpoint(
            "SageMakerApiEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SAGEMAKER_API,
        )
        self.vpc.add_interface_endpoint(
            "CloudWatchLogsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
        )
        self.vpc.add_gateway_endpoint(
            "S3Endpoint", service=ec2.GatewayVpcEndpointAwsService("s3")
        )
        core.CfnOutput(self, "VPC ID", value=self.vpc.vpc_id)
