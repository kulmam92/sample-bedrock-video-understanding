from aws_cdk import (
    NestedStack,
    aws_sagemaker as sagemaker,
    aws_iam as _iam,
    custom_resources as cr,
    aws_lambda as _lambda,
    aws_s3_deployment as _s3_deployment,
    aws_s3 as _s3,
    RemovalPolicy,
    aws_kms as _kms,
    Token
)
from constructs import Construct
import os
from analytics.constant import *
import base64

class AnalyticsStack(NestedStack):
    account_id = None
    region = None

    s3_bucket_name_data_str = None
    notebook_instance_name = f"{RES_NAME_PREFIX}analytics"
    
    def __init__(self, scope: Construct, construct_id: str, s3_bucket_name_data_str: str,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.account_id=os.environ.get("CDK_DEFAULT_ACCOUNT")
        self.region=os.environ.get("CDK_DEFAULT_REGION")

        self.s3_bucket_name_data_str = s3_bucket_name_data_str
        
        self.deploy_sagemaker_notebook()

    def deploy_sagemaker_notebook(self):
        instance_type = "ml.t3.large"
        local_code_folder = os.path.join("../source/", f"analytics/sample")
        s3_prefix_code = "analytics"

        # Upload analytics sample code to s3 staging bucket
        _s3_deployment.BucketDeployment(
            self, 
            "DeployNotebooks",
            sources=[_s3_deployment.Source.asset(local_code_folder)],
            destination_bucket=_s3.Bucket.from_bucket_name(self, "StagingBucket", bucket_name=self.s3_bucket_name_data_str),
            destination_key_prefix=s3_prefix_code,  # optional, adds a prefix inside the bucket
            memory_limit=1024
        )

        # Create lifecycle config
        # Script to download S3 code to the Notebook instance
        lifecycle_script = f"""#!/bin/bash
set -e
aws s3 sync s3://{self.s3_bucket_name_data_str}/{s3_prefix_code} /home/ec2-user/SageMaker/
"""

        lifecycle_config = sagemaker.CfnNotebookInstanceLifecycleConfig(
            self,
            "CopyCodeNotebookLifecycle",
            notebook_instance_lifecycle_config_name="bedrock-mm-copy-code-config",
            on_create=[
                 sagemaker.CfnNotebookInstanceLifecycleConfig.NotebookInstanceLifecycleHookProperty(
                        content=base64.b64encode(lifecycle_script.encode("utf-8")).decode("utf-8")
                    )
                ]
        )

        # Launch notebook instance with config
        sagemaker_role = _iam.Role(
            self, "sagemaker-notebook-role",
            assumed_by=_iam.ServicePrincipal("sagemaker.amazonaws.com"),
            inline_policies={f"sagemaker-notebook-poliy": _iam.PolicyDocument(
                statements=[      
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["sagemaker:*"],
                        resources=["*"]
                    ),      
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:ListBucket","s3:GetObject","s3:PutObject","s3:DeleteObject"],
                        resources=[f"arn:aws:s3:::{self.s3_bucket_name_data_str}",f"arn:aws:s3:::{self.s3_bucket_name_data_str}/*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["bedrock:InvokeModel","bedrock:GetAsyncInvoke"],
                        resources=[
                            "arn:aws:bedrock:*:*:foundation-model/*",
                            "arn:aws:bedrock:*:*:async-invoke/*",
                            "arn:aws:bedrock:*:*:inference-profile/*"
                        ]
                    ),
                    _iam.PolicyStatement(
                        actions=["dynamodb:DeleteItem","dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem","dynamodb:DescribeTable","dynamodb:BatchWriteItem"],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_FRAME_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_SHOT_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TRANS_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TRANS_TABLE}",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_FRAME_TABLE}",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_SHOT_TABLE}"
                        ]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["lambda:InvokeFunction"],
                        resources=[
                            f"arn:aws:lambda:{self.region}:{self.account_id}:function:{RES_NAME_PREFIX}*"
                        ]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogGroup"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:*"]
                    ),
                ]
            )}
        )
        
        # Create a KMS Key for encryption
        notebook_kms_key = _kms.Key(
            self, "notebook-kms-key",
            description="KMS key for SageMaker Notebook Instance encryption",
            enable_key_rotation=True,
            alias="alias/sagemaker-notebook-key"
        )
        notebook_kms_key.grant_decrypt(sagemaker_role)
        notebook_kms_key.grant_encrypt(sagemaker_role)

        notebook = sagemaker.CfnNotebookInstance(
            self,
            "analytics-notebook",
            notebook_instance_name=self.notebook_instance_name,
            instance_type=instance_type,
            role_arn=sagemaker_role.role_arn,
            direct_internet_access="Enabled",
            lifecycle_config_name=lifecycle_config.notebook_instance_lifecycle_config_name,
            kms_key_id=notebook_kms_key.key_id,
            volume_size_in_gb=5,
            root_access="Enabled"
        )

        notebook.apply_removal_policy(RemovalPolicy.DESTROY)
