from aws_cdk import (
    Stack,
    NestedStack,
    Size,
    aws_ec2 as ec2,
    CfnParameter as _cfnParameter,
    aws_cognito as _cognito,
    aws_s3 as _s3,
    aws_s3_notifications as _s3_noti,
    aws_lambda as _lambda,
    aws_apigateway as _apigw,
    aws_iam as _iam,
    aws_sqs as _sqs,
    aws_opensearchservice as opensearch,
    aws_lambda_event_sources as lambda_event_sources,
    aws_dynamodb as _dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    Duration,
    aws_stepfunctions as _aws_stepfunctions,
    RemovalPolicy,
    custom_resources as cr,
    CustomResource,
    Token,
    Fn,
    CfnResource,
    custom_resources,
    aws_logs as logs,
    CfnCondition as condition,
    CfnOutput
)
from aws_cdk.aws_apigateway import IdentitySource
from aws_cdk.aws_kms import Key
from aws_cdk.aws_ec2 import SecurityGroup

from constructs import Construct
import os
import uuid
import json
from nova_service.constant import *

class NovaServiceStack(NestedStack):
    account_id = None
    region = None

    api_gw_base_url = None
    api_gw_key = None

    cognito_user_pool_id = None
    cognito_app_client_id = None
    cognito_app_client_id = None
    cognito_authorizer = None

    s3_bucket_name_mm = None
    s3_mm_bucket = None

    boto3_layer = None
    nova_layer = None
    moviepy_layer = None

    api = None
    
    def __init__(self, scope: Construct, construct_id: str, cognito_user_pool_id: str, cognito_app_client_id: str,
            s3_bucket_name_mm, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.account_id=os.environ.get("CDK_DEFAULT_ACCOUNT")
        self.region=os.environ.get("CDK_DEFAULT_REGION")
        
        self.s3_bucket_name_mm = s3_bucket_name_mm
        self.cognito_user_pool_id = cognito_user_pool_id
        self.cognito_app_client_id = cognito_app_client_id

        self.deploy_dynamodb()
        self.deploy_s3()
        self.deploy_cognito()
        self.deploy_lambda()
        self.deploy_apigw_lambda()

    def deploy_dynamodb(self):
        # Create DynamoDB tables
        # Video task table                           
        video_task_table = _dynamodb.Table(self, 
            id='video-task-table', 
            table_name=DYNAMO_VIDEO_TASK_TABLE, 
            partition_key=_dynamodb.Attribute(name='Id', type=_dynamodb.AttributeType.STRING),
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY
        )
        video_task_table.add_global_secondary_index(
            index_name="RequestBy-index",
            partition_key=_dynamodb.Attribute(
                name="RequestBy",
                type=_dynamodb.AttributeType.STRING
            ),
            projection_type=_dynamodb.ProjectionType.ALL 
        )

    def deploy_s3(self):
        self.s3_mm_bucket = _s3.Bucket.from_bucket_name(self, "NovaMmeBucket", bucket_name=self.s3_bucket_name_mm)

    def deploy_cognito(self):
        user_pool = _cognito.UserPool.from_user_pool_id(
            self, "WebUserPool",
            user_pool_id=self.cognito_user_pool_id
        )

        #self.cognito_user_pool_id = user_pool.user_pool_id
        web_client = _cognito.UserPoolClient.from_user_pool_client_id(
            self, "NovaMmSrvAppClient",
            user_pool_client_id=self.cognito_app_client_id
        )

        # Create API Gateway CognitioUeserPoolAuthorizer
        self.cognito_authorizer = _apigw.CognitoUserPoolsAuthorizer(self, f"WebAuth", 
            cognito_user_pools=[user_pool],
            identity_source=IdentitySource.header('Authorization')
        )

    def deploy_lambda(self):
        # Load S3 layer generated from the provision step
        layer_bucket = _s3.Bucket.from_bucket_name(self, "LayerBucket", bucket_name=self.s3_bucket_name_mm)
        self.boto3_layer = _lambda.LayerVersion(self, 'Boto3PyLayer',
            code=_lambda.S3Code(bucket=layer_bucket, key=LAMBDA_LAYER_SOURCE_S3_KEY_BOTO3),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_13],
            description="Python 3.12 with boto3 for S3 vectors"
        )
        self.moviepy_layer = _lambda.LayerVersion(self, 'MoviePyLayer',
            code=_lambda.S3Code(bucket=layer_bucket, key=LAMBDA_LAYER_SOURCE_S3_KEY_MOVIEPY),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_13],
            description="Python 3.12 with movie.py"
        )
        # Nova S3 listener Lambda
        # Function name: nova-srv-s3-listener
        lambda_nova_s3_listener_role = _iam.Role(
            self, "NovaSrvLambdaS3ListenerRole",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={"nova-srv-s3-listener-poliy": _iam.PolicyDocument(
                statements=[
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:ListBucket","s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListMultipartUploadParts","s3:ListBucketMultipartUploads"],
                        resources=[f"arn:aws:s3:::{self.s3_bucket_name_mm}",f"arn:aws:s3:::{self.s3_bucket_name_mm}/*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3vectors:*"],
                        resources=[f"arn:aws:s3vectors:{self.region}:{self.account_id}:bucket/{S3_VECTOR_BUCKET_NOVA}",f"arn:aws:s3vectors:{self.region}:{self.account_id}:bucket/{S3_VECTOR_BUCKET_NOVA}/*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogGroup"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/lambda/{LAMBDA_NAME_PREFIX}nova-srv-s3-listener:*"]
                    ),
                    _iam.PolicyStatement(
                        actions=["dynamodb:DeleteItem","dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}",
                        ]
                    ) 
                ]
            )}

        )
        lamabd_s3_listener = _lambda.Function(self, 
            id='nova_srv_s3_listener_function', 
            function_name=f"{LAMBDA_NAME_PREFIX}nova-srv-s3-listener", 
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler='nova-srv-s3-listener.lambda_handler',
            code=_lambda.Code.from_asset(os.path.join("../source/", "nova_service/lambda/nova-srv-s3-listener")),
            timeout=Duration.seconds(180),
            role=lambda_nova_s3_listener_role,
            memory_size=10240,
            layers=[self.boto3_layer],
            environment={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'NOVA_S3_VECTOR_BUCKET': S3_VECTOR_BUCKET_NOVA,
                'NOVA_S3_VECTOR_INDEX': S3_VECTOR_INDEX_NOVA,
            },
        )

        # Add S3 trigger using EventBridge (works cross-stack)
        # Grant S3 access to trigger the Lambda function
        self.s3_mm_bucket.grant_read(lamabd_s3_listener)
        
        # Create EventBridge rule for S3 events
        s3_event_rule = events.Rule(
            self, "S3ObjectCreatedRule",
            description="Trigger Lambda when .jsonl files are created in tasks/ prefix",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {
                        "name": [self.s3_bucket_name_mm]
                    },
                    "object": {
                        "key": [{
                            "wildcard": "tasks/*/nova-mme/*.jsonl"
                        }]
                    }
                }
            )
        )
        
        # Add Lambda as target for the EventBridge rule
        s3_event_rule.add_target(targets.LambdaFunction(lamabd_s3_listener))
        
        # Grant EventBridge permission to invoke the Lambda
        lamabd_s3_listener.add_permission(
            "AllowEventBridgeInvoke",
            principal=_iam.ServicePrincipal("events.amazonaws.com"),
            source_arn=s3_event_rule.rule_arn
        )

        # utility function - get video thumbnail
        # Lambda: nova-srv-get-video-metadata
        lambda_nova_get_metadata_role = _iam.Role(
            self, "NovaSrvLambdaMetaDataRole",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={"nova-srv-get-video-metadata-poliy": _iam.PolicyDocument(
                statements=[
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:ListBucket","s3:GetObject","s3:PutObject","s3:DeleteObject"],
                        resources=[f"arn:aws:s3:::{self.s3_bucket_name_mm}",f"arn:aws:s3:::{self.s3_bucket_name_mm}/*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["bedrock:InvokeModel","bedrock:GetAsyncInvoke", "bedrock:Converse"],
                        resources=[
                            "arn:aws:bedrock:*:*:foundation-model/*",
                            "arn:aws:bedrock:*:*:async-invoke/*",
                            "arn:aws:bedrock:*:*:inference-profile/*"
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
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/lambda/{LAMBDA_NAME_PREFIX}nova-srv-get-video-metadata:*"]
                    ),
                    _iam.PolicyStatement(
                        actions=["dynamodb:DeleteItem","dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}",
                        ]
                    )
                ]
            )}
        )
        self.lambda_nova_get_video_metadata = _lambda.Function(self, 
            id='NovaSrvGetVideoMetadataLambda', 
            function_name=f"{LAMBDA_NAME_PREFIX}nova-srv-get-video-metadata", 
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler='nova-srv-get-video-metadata.lambda_handler',
            code=_lambda.Code.from_asset(os.path.join("../source/", "nova_service/lambda/nova-srv-get-video-metadata")),
            timeout=Duration.seconds(900),
            memory_size=3008,
            ephemeral_storage_size=Size.mebibytes(10240),
            environment={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'VIDEO_SAMPLE_CHUNK_DURATION_S': "600",
                'VIDEO_SAMPLE_S3_PREFIX': VIDEO_SAMPLE_S3_PREFIX,
                'VIDEO_SAMPLE_S3_BUCKET': self.s3_bucket_name_mm,
                'MODEL_ID_IMAGE_UNDERSTANDING': MODEL_ID_IMAGE_UNDERSTANDING
            },
            role=lambda_nova_get_metadata_role,
            layers=[self.moviepy_layer],
        )

    def deploy_apigw_lambda(self):
        # API Gateway - start
        api = _apigw.RestApi(self, f"{API_NAME_PREFIX}Service",
                                rest_api_name=f"{API_NAME_PREFIX}-service",
                                cloud_watch_role=True,
                                cloud_watch_role_removal_policy=RemovalPolicy.DESTROY,
                                deploy_options=_apigw.StageOptions(
                                        tracing_enabled=True,
                                        access_log_destination=_apigw.LogGroupLogDestination(logs.LogGroup(self, f"ApiGatewayBedrockMmSrvAccessLog")),
                                        access_log_format=_apigw.AccessLogFormat.clf(),
                                        method_options={
                                            "/*/*": _apigw.MethodDeploymentOptions( # This special path applies to all resource paths and all HTTP methods
                                                logging_level=_apigw.MethodLoggingLevel.INFO,)
                                    }                               
                                ),   
                            )
        
        # Create API Key and associated plan
        plan = api.add_usage_plan("UsagePlan",
            name="Easy",
            throttle=_apigw.ThrottleSettings(
                rate_limit=10,
                burst_limit=2
            )
        )
        key = api.add_api_key("ApiKey")
        plan.add_api_key(key)
        self.api_gw_key = key

        # Create resources
        v1 = api.root.add_resource("v1")
        nova = v1.add_resource("nova")
        embed = nova.add_resource("embedding")
        
        self.api_gw_base_url = api.url
                                     
        # POST v1/embedding/delete-task
        # Lambda: nova-srv-delete-video-task
        lambda_nova_delete_task_role = _iam.Role(
            self, "NovaLambdaDeleteTaskRole",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={"nova-srv-delete-video-task-poliy": _iam.PolicyDocument(
                statements=[              
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogGroup"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/lambda/{LAMBDA_NAME_PREFIX}nova-srv-delete-video-task:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:ListBucket","s3:GetObject","s3:PutObject","s3:DeleteObject"],
                        resources=[f"arn:aws:s3:::{self.s3_bucket_name_mm}",f"arn:aws:s3:::{self.s3_bucket_name_mm}/*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3vectors:*"],
                        resources=[f"arn:aws:s3vectors:{self.region}:{self.account_id}:bucket/{S3_VECTOR_BUCKET_NOVA}", f"arn:aws:s3vectors:{self.region}:{self.account_id}:bucket/{S3_VECTOR_BUCKET_NOVA}/*"]
                    ),
                    _iam.PolicyStatement(
                        actions=["dynamodb:DeleteItem","dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}",
                        ]
                    )
                ]
            )}
        )
        self.create_api_endpoint(id='NovaLambdaDeleteTaskEp', 
            root=embed, path1="delete-task", method="POST", auth=self.cognito_authorizer, 
            role=lambda_nova_delete_task_role, 
            lambda_file_name="nova-srv-delete-video-task", 
            memory_m=1024, timeout_s=30, ephemeral_storage_size=512,
            evns={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'NOVA_S3_VECTOR_BUCKET': S3_VECTOR_BUCKET_NOVA,
                'NOVA_S3_VECTOR_INDEX': S3_VECTOR_INDEX_NOVA,
            },
            layers=[self.boto3_layer]
        )   

        # POST /v1/embedding/get-task-clips
        # Lambda: nova-srv-get-task-clips
        lambda_nova_get_task_clips_role = _iam.Role(
            self, "NovaLambdaGetTaskRole",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={"nova-srv-get-task-clips-poliy": _iam.PolicyDocument(
                statements=[
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:ListBucket","s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListMultipartUploadParts","s3:ListBucketMultipartUploads"],
                        resources=[f"arn:aws:s3:::{self.s3_bucket_name_mm}",f"arn:aws:s3:::{self.s3_bucket_name_mm}/*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogGroup"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/lambda/{LAMBDA_NAME_PREFIX}nova-srv-get-task-clips:*"]
                    ),
                    _iam.PolicyStatement(
                        actions=["dynamodb:DeleteItem","dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}",
                        ]
                    ) 
                ]
            )}
        )
        self.create_api_endpoint(id='NovaLambdaGetTaskClipsEp', root=embed, path1="get-task-clips", method="POST", auth=self.cognito_authorizer, 
                role=lambda_nova_get_task_clips_role, 
                lambda_file_name="nova-srv-get-task-clips",
                memory_m=1024, timeout_s=30, ephemeral_storage_size=512,
            evns={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
            })        
        
        # POST /v1/embedding/nova-srv-search-vector
        # Lambda: nova-srv-search-vector
        lambda_es_get_task_frames_role = _iam.Role(
            self, "NovaLambdaSearchVectorRole",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={"nova-srv-search-vector-poliy": _iam.PolicyDocument(
                statements=[
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:ListBucket","s3:GetObject","s3:PutObject"],
                        resources=[f"arn:aws:s3:::{self.s3_bucket_name_mm}",f"arn:aws:s3:::{self.s3_bucket_name_mm}/*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogGroup"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/lambda/{LAMBDA_NAME_PREFIX}nova-srv-search-vector:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3vectors:*"],
                        resources=[f"arn:aws:s3vectors:{self.region}:{self.account_id}:bucket/{S3_VECTOR_BUCKET_NOVA}",f"arn:aws:s3vectors:{self.region}:{self.account_id}:bucket/{S3_VECTOR_BUCKET_NOVA}/*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["bedrock:InvokeModel","bedrock:GetAsyncInvoke"],
                        resources=["arn:aws:bedrock:*:*:*"]
                    ),
                    _iam.PolicyStatement(
                        actions=["dynamodb:DeleteItem","dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}",
                        ]
                    )              
                ]
            )}
        )
            
        self.create_api_endpoint(id='NovaLambdaSearchVectorEp', root=embed, path1="search-task-vector", method="POST", auth=self.cognito_authorizer, 
                role=lambda_es_get_task_frames_role, 
                lambda_file_name="nova-srv-search-vector",
                memory_m=1024, timeout_s=180, ephemeral_storage_size=1024,
            evns={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'S3_PRE_SIGNED_URL_EXPIRY_S': S3_PRE_SIGNED_URL_EXPIRY_S,
                'NOVA_S3_VECTOR_BUCKET': S3_VECTOR_BUCKET_NOVA,
                'NOVA_S3_VECTOR_INDEX':S3_VECTOR_INDEX_NOVA,
                'S3_BUCKET_DATA': self.s3_bucket_name_mm,
                'MODEL_ID': MODEL_ID_BEDROCK_MME
            },
            layers=[self.boto3_layer]
            )   

        # POST /v1/embedding/start-task
        # Lambda: nova-srv-start-task
        lambda_nova_start_task_role = _iam.Role(
            self, "NovaLambdaStartTaskRole",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={"nova-srv-start-task-poliy": _iam.PolicyDocument(
                statements=[
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:ListBucket","s3:GetObject","s3:PutObject"],
                        resources=[f"arn:aws:s3:::{self.s3_bucket_name_mm}",f"arn:aws:s3:::{self.s3_bucket_name_mm}/*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogGroup"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/lambda/{LAMBDA_NAME_PREFIX}nova-srv-start-task:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["bedrock:InvokeModel"],
                        resources=["arn:aws:bedrock:*:*:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["lambda:InvokeFunction"],
                        resources=["*"]
                    ),
                    _iam.PolicyStatement(
                        actions=["dynamodb:DeleteItem","dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}",
                        ]
                    )              
                ]
            )}
        )
            
        self.create_api_endpoint(id='NovaLambdaStartTaskEp', root=embed, path1="start-task", method="POST", auth=self.cognito_authorizer, 
                role=lambda_nova_start_task_role, 
                lambda_file_name="nova-srv-start-task",
                memory_m=128, timeout_s=30, ephemeral_storage_size=512,
            evns={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'LAMBDA_FUN_NAME_VIDEO_METADATA': self.lambda_nova_get_video_metadata.function_name,
                'DEFAULT_NOVA_MME_MODEL_ID': MODEL_ID_BEDROCK_MME,
                'EMBEDDING_DIM':S3_VECTOR_INDEX_DIM_NOVA,
            })      

        # POST /v1/nova/embedding/get-task
        # Lambda: nova-srv-get-video-task
        lambda_nova_get_task_role = _iam.Role(
            self, "NovaSrvLambdaGetTaskRole",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={"nova-srv-get-task-poliy": _iam.PolicyDocument(
                statements=[
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:ListBucket","s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListMultipartUploadParts","s3:ListBucketMultipartUploads"],
                        resources=[f"arn:aws:s3:::{self.s3_bucket_name_mm}",f"arn:aws:s3:::{self.s3_bucket_name_mm}/*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogGroup"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/lambda/{LAMBDA_NAME_PREFIX}nova-srv-get-video-task:*"]
                    ),
                    _iam.PolicyStatement(
                        actions=["dynamodb:DeleteItem","dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}",
                        ]
                    ) 
                ]
            )}
        )
        self.create_api_endpoint(id='NovaSrvGetTaskEp', root=embed, path1="get-task", method="POST", auth=self.cognito_authorizer, 
                role=lambda_nova_get_task_role, 
                lambda_file_name="nova-srv-get-video-task",
                memory_m=128, timeout_s=20, ephemeral_storage_size=1024,
            evns={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'S3_PRESIGNED_URL_EXPIRY_S':S3_PRE_SIGNED_URL_EXPIRY_S,
            })           
        
        # POST /v1/nova/embedding/search-task
        # Lambda: nova-srv-get-video-tasks 
        lambda_es_get_tasks_role = _iam.Role(
            self, "NovaSrvLambdaGetTasksRole",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={"nova-srv-get-tasks-poliy": _iam.PolicyDocument(
                statements=[
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:ListBucket","s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListMultipartUploadParts","s3:ListBucketMultipartUploads"],
                        resources=[f"arn:aws:s3:::{self.s3_bucket_name_mm}",f"arn:aws:s3:::{self.s3_bucket_name_mm}/*"]
                    ),                    
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogGroup"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/lambda/{LAMBDA_NAME_PREFIX}nova-srv-get-video-tasks:*"]
                    ),
                    _iam.PolicyStatement(
                        actions=["dynamodb:DeleteItem","dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}",
                        ]
                    ) 
                ]
            )}
        )
        self.create_api_endpoint(id='NovaSrvGetTasksEp', root=embed, path1="search-task", method="POST", auth=self.cognito_authorizer, 
                role=lambda_es_get_tasks_role,
                lambda_file_name="nova-srv-get-video-tasks",
                memory_m=128, timeout_s=10, ephemeral_storage_size=1024,
                evns={
                    'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                    'S3_PRE_SIGNED_URL_EXPIRY_S': S3_PRE_SIGNED_URL_EXPIRY_S,
                }
        )

        # POST /v1/util/nova-srv-manage-s3-presigned-url
        # Lambda: nova-srv-manage-s3-presigned-url

        util = v1.add_resource("util")

        lambda_es_manage_s3_url_role = _iam.Role(
            self, "UtilLambdaManageS3PresignedUrlRole",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={"util-nova-srv-manage-s3-presigned-url-poliy": _iam.PolicyDocument(
                statements=[
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:ListBucket","s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListMultipartUploadParts","s3:ListBucketMultipartUploads"],
                        resources=[f"arn:aws:s3:::{self.s3_bucket_name_mm}",f"arn:aws:s3:::{self.s3_bucket_name_mm}/*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogGroup"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:*"]
                    ),
                    _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                        resources=[f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/lambda/{LAMBDA_NAME_PREFIX}nova-srv-manage-s3-presigned-url:*"]
                    ),
                    _iam.PolicyStatement(
                        actions=["ec2:DescribeNetworkInterfaces", "ec2:CreateNetworkInterface", "ec2:DeleteNetworkInterface",],
                        resources=["*"]
                    )
                ]
            )}
        )
        self.create_api_endpoint(id='UtilManageS3UrlEp', root=util, path1="nova-srv-manage-s3-presigned-url", method="POST", auth=self.cognito_authorizer, 
                role=lambda_es_manage_s3_url_role,
                lambda_file_name="nova-srv-manage-s3-presigned-url",
                memory_m=128, timeout_s=10, ephemeral_storage_size=512,
                evns={
                'S3_PRESIGNED_URL_EXPIRY_S': S3_PRE_SIGNED_URL_EXPIRY_S,
                'VIDEO_UPLOAD_S3_PREFIX': VIDEO_UPLOAD_S3_PREFIX,
                'VIDEO_UPLOAD_S3_BUCKET': self.s3_bucket_name_mm
                }
            )   

    def create_api_endpoint(self, id, root, path1, method, auth, role, lambda_file_name, memory_m, timeout_s, ephemeral_storage_size, evns, layers=None):
        lambda_function = _lambda.Function(self, 
            id=id, 
            function_name=f"{LAMBDA_NAME_PREFIX}{lambda_file_name}", 
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler=f'{lambda_file_name}.lambda_handler',
            code=_lambda.Code.from_asset(os.path.join("../source/", f"nova_service/lambda/{lambda_file_name}")),
            timeout=Duration.seconds(timeout_s),
            memory_size=memory_m,
            ephemeral_storage_size=Size.mebibytes(ephemeral_storage_size),
            role=role,
            environment=evns,
            layers=layers,
        )

        resource = root.add_resource(
                path1, 
                default_cors_preflight_options=_apigw.CorsOptions(
                allow_methods=['POST', 'OPTIONS'],
                allow_origins=_apigw.Cors.ALL_ORIGINS),
        )

        method = resource.add_method(
            method, 
            _apigw.LambdaIntegration(
                lambda_function,
                proxy=False,
                integration_responses=[
                    _apigw.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            'method.response.header.Access-Control-Allow-Origin': "'*'"
                        }
                    )
                ]
            ),
            method_responses=[
                _apigw.MethodResponse(
                    status_code="200",
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True
                    }
                )
            ],
            authorizer=auth,
            authorization_type=_apigw.AuthorizationType.COGNITO
        )