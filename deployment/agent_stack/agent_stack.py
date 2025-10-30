from aws_cdk import (
    NestedStack,
    aws_codebuild as _codebuild,
    aws_iam as _iam,
    aws_lambda as _lambda,
    custom_resources as cr,
    Duration,
    aws_s3_assets as _s3_assets,
    Fn
)
from constructs import Construct
import os, json

class AgentStack(NestedStack):
    account_id = None
    region = None

    agentcore_runtime_arn = None

    def __init__(self, scope: Construct, construct_id: str, 
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.account_id=os.environ.get("CDK_DEFAULT_ACCOUNT")
        self.region=os.environ.get("CDK_DEFAULT_REGION")

        source_asset = _s3_assets.Asset(
            self,
            "AgentCoreSourceCode",
            path="../source/agent",   # <-- local React project folder
            exclude=["Dockerfile", ".dockerignore",".bedrock_agentcore.yaml", ".venv", "test.py"]

        )

        # Role for CodeBuild
        codebuild_role = _iam.Role(
            self, "AgentCoreCodeBuildProjectRole",
            assumed_by=_iam.ServicePrincipal("codebuild.amazonaws.com"),
            inline_policies={"agentcore-codebuild-project-poliy": _iam.PolicyDocument(
                statements=[
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=[
                            "iam:CreateRole",
                            "iam:DeleteRole",
                            "iam:GetRole",
                            "iam:PutRolePolicy",
                            "iam:DeleteRolePolicy",
                            "iam:AttachRolePolicy",
                            "iam:DetachRolePolicy",
                            "iam:TagRole",
                            "iam:ListRolePolicies",
                            "iam:ListAttachedRolePolicies"
                        ],
                        resources=[
                            "arn:aws:iam::*:role/*BedrockAgentCore*",
                            "arn:aws:iam::*:role/service-role/*BedrockAgentCore*"
                        ]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=[
                            "iam:PassRole"
                        ],
                        resources=[
                            "arn:aws:iam::*:role/AmazonBedrockAgentCore*",
                            "arn:aws:iam::*:role/service-role/AmazonBedrockAgentCore*"                       
                        ]                    
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=[
                            "codebuild:*"
                        ],
                        resources=[
                            "*"                        
                        ]                    
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                         actions=["iam:PassRole"],
                        resources=[
                            "arn:aws:iam::*:role/AmazonBedrockAgentCore*",
                            "arn:aws:iam::*:role/service-role/AmazonBedrockAgentCore*"
                        ]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=[
                            "logs:GetLogEvents",
                            "logs:DescribeLogGroups",
                            "logs:DescribeLogStreams"
                        ],
                        resources=[
                            "arn:aws:logs:*:*:log-group:/aws/bedrock-agentcore/*",
                            "arn:aws:logs:*:*:log-group:/aws/codebuild/*",
                            "arn:aws:logs:*:*:log-group:*"
                        ]
                    ),
                    _iam.PolicyStatement(
                        actions=[
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:ListBucket",
                            "s3:CreateBucket",
                            "s3:PutLifecycleConfiguration"
                        ],
                        resources=[
                            "arn:aws:s3:::bedrock-agentcore-*",
                            "arn:aws:s3:::bedrock-agentcore-*/*",
                            f"{source_asset.bucket.bucket_arn}*",
                            f"{source_asset.bucket.bucket_arn}*/*"
                        ]
                    ),
                    _iam.PolicyStatement(
                        actions=[
                            "codebuild:StartBuild"
                        ],
                        resources=["*"]
                    ),
                    _iam.PolicyStatement(
                        actions=[
                            "ecr:CreateRepository",
                            "ecr:DescribeRepositories",
                            "ecr:GetRepositoryPolicy",
                            "ecr:InitiateLayerUpload",
                            "ecr:CompleteLayerUpload",
                            "ecr:PutImage",
                            "ecr:UploadLayerPart",
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchGetImage",
                            "ecr:ListImages",
                            "ecr:BatchDeleteImage",
                            "ecr:DeleteRepository",
                            "ecr:TagResource"
                        ],
                        resources=[
                            "arn:aws:ecr:*:*:repository/bedrock-agentcore-*"
                        ]
                    ),
                    _iam.PolicyStatement(
                        actions=[
                            "ecr:GetAuthorizationToken"
                        ],
                        resources=[
                            "*"
                        ]
                    ),
                    _iam.PolicyStatement(
                        actions=[
                            "bedrock-agentcore:*"
                        ],
                        resources=[
                            "arn:aws:bedrock-agentcore:*:*:*/*"
                        ]
                    ),
                    _iam.PolicyStatement(
                        actions=[
                            "sts:GetCallerIdentity"
                        ],
                        resources=[
                            "*"
                        ]
                    )   
                ]
            )})

        project = _codebuild.Project(
            self,
            "bedrock-mm-agentcore-build",
            role=codebuild_role,
            source=_codebuild.Source.s3(
                bucket=source_asset.bucket,
                path=source_asset.s3_object_key,
            ),
            environment=_codebuild.BuildEnvironment(
                build_image=_codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True,
            ),
            build_spec=_codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "install": {
                        "commands": [
                            "echo install requirements",
                            "pip install -r requirements.txt || true"
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo run python deploy.py",
                            "python deploy.py"
                        ]
                    }
                }
            }),
        )

        # Lambda to trigger CodeBuild and get output
        lambda_fn = _lambda.Function(
            self, "CodeBuildInvoker",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=_lambda.Code.from_inline("""
import boto3
import time
import json

def handler(event, context):
    project_name = event['ProjectName']
    agent_name = event['AgentName']

    cb = boto3.client('codebuild')
    agentcore = boto3.client('bedrock-agentcore-control')

    # Start CodeBuild
    build = cb.start_build(projectName=project_name)
    build_id = build['build']['id']

    # Wait for completion
    while True:
        status = cb.batch_get_builds(ids=[build_id])['builds'][0]['buildStatus']
        if status in ['SUCCEEDED', 'FAILED', 'FAULT', 'STOPPED', 'TIMED_OUT']:
            break
        time.sleep(5)

    if status != 'SUCCEEDED':
        raise Exception(f"Build failed: {status}")

    # Get agentcore runtime id and arn

    output = {}
    response = agentcore.list_agent_runtimes(
        maxResults=100,
    )
    if response and "agentRuntimes" in response:
        for rt in response["agentRuntimes"]:
            if rt["agentRuntimeName"] == agent_name:
                output = rt["agentRuntimeArn"]
                break

    return output
            """),
            timeout=Duration.minutes(15),
        )

        source_asset.grant_read(lambda_fn)
        
        lambda_fn.add_to_role_policy(
            _iam.PolicyStatement(
                actions=["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
                resources=[project.project_arn]
            )
        ),
        lambda_fn.add_to_role_policy(
            _iam.PolicyStatement(
                actions=["bedrock-agentcore:*"],
                resources=["*"]
            )
        )

        # Custom Resource
        build_output = cr.AwsCustomResource(
            self, "GetCodeBuildOutput",
            on_create=cr.AwsSdkCall(
                service="Lambda",
                action="Invoke",
                parameters={
                    "FunctionName": lambda_fn.function_name,
                    "Payload": json.dumps({
                        "ProjectName": project.project_name,
                        "AgentName": "bedrock_mm_video_understanding_agent"
                    })
                },
                physical_resource_id=cr.PhysicalResourceId.of("CodeBuildOutput")
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                _iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=[lambda_fn.function_arn]
                )
            ])
        )

        output = build_output.get_response_field("Payload")
        # Access the output directly - no need to split by quotes since Lambda returns the ARN directly
        self.agentcore_runtime_arn = output
