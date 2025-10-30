from aws_cdk import (
    NestedStack,
    Size,
    aws_cognito as _cognito,
    aws_s3 as _s3,
    aws_events as _events,
    aws_events_targets as _targets,
    aws_lambda as _lambda,
    aws_apigateway as _apigw,
    aws_iam as _iam,
    aws_dynamodb as _dynamodb,
    Duration,
    RemovalPolicy,
    aws_logs as logs,
)
from aws_cdk.aws_apigateway import IdentitySource

from constructs import Construct
import os, re
from tlabs_service.constant import *

class TlabsServiceStack(NestedStack):
    account_id = None
    region = None
    instance_hash = None

    api_gw_base_url = None
    api_gw_key = None

    cognito_user_pool_id = None
    cognito_app_client_id = None
    cognito_authorizer = None

    s3_bucket_name_mm = None
    s3_mm_bucket = None

    boto3_layer = None
    tlabs_layer = None
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
        self.s3_mm_bucket = _s3.Bucket.from_bucket_name(self, "TlabsMmBucket", bucket_name=self.s3_bucket_name_mm)
        
        # Enable EventBridge notifications on the S3 bucket
        # Note: This requires the bucket to have EventBridge notifications enabled
        # This can be done via AWS CLI: aws s3api put-bucket-notification-configuration --bucket BUCKET_NAME --notification-configuration '{"EventBridgeConfiguration": {}}'


    def deploy_cognito(self):
        user_pool = _cognito.UserPool.from_user_pool_id(
            self, "WebUserPool",
            user_pool_id=self.cognito_user_pool_id
        )

        web_client = _cognito.UserPoolClient.from_user_pool_client_id(
            self, "TlabsMmSrvAppClient",
            user_pool_client_id=self.cognito_app_client_id
        )

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
            description="Python 3.13 with boto3 for S3 vectors"
        )
        self.moviepy_layer = _lambda.LayerVersion(self, 'MoviePyLayer',
            code=_lambda.S3Code(bucket=layer_bucket, key=LAMBDA_LAYER_SOURCE_S3_KEY_MOVIEPY),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_13],
            description="Python 3.13 with movie.py"
        )

        # Tlabs EventBridge listener Lambda
        # Function name: tlabs-srv-s3-listener
        lambda_key = "tlabs-srv-s3-listener" 
        lambda_role = self.create_role(lambda_key, ["s3","dynamodb","s3vectors","events"])
        lambda_fun = self.create_lambda(
            lambda_key, 
            lambda_role, 
            {
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'TLABS_S3_VECTOR_BUCKET': S3_VECTOR_BUCKET_TLABS,
                'TLABS_S3_VECTOR_INDEX': S3_VECTOR_INDEX_TLABS,
            }, 
            timeout_s=180, memory_size=10240, ephemeral_storage_size=1024,
            layers=[self.boto3_layer],
        )

        # Add EventBridge trigger
        if self.s3_mm_bucket:
            # Grant S3 access to trigger the Lambda function
            self.s3_mm_bucket.grant_read(lambda_fun)
            
            # Create EventBridge rule for S3 object created events
            s3_event_rule = _events.Rule(
                self, "TlabsS3ObjectCreatedRule",
                event_pattern=_events.EventPattern(
                    source=["aws.s3"],
                    detail_type=["Object Created"],
                    detail={
                        "bucket": {"name": [self.s3_bucket_name_mm]},
                        "object": {
                            "key": [{
                                "wildcard": "tasks/*/tlabs/*output.json"
                            }]
                        }
                    }
                )
            )
            
            # Add Lambda as target for the EventBridge rule
            s3_event_rule.add_target(_targets.LambdaFunction(lambda_fun))

        # utility function - get video thumbnail
        # Lambda: tlabs-srv-get-video-metadata
        lambda_key = "tlabs-srv-get-video-metadata" 
        lambda_role = self.create_role(lambda_key, ["s3","dynamodb","s3vectors"])
        self.lambda_tlabs_get_video_metadata = self.create_lambda(
            lambda_key, 
            lambda_role, 
            {
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'MODEL_ID_IMAGE_UNDERSTANDING': MODEL_ID_IMAGE_UNDERSTANDING,
                'VIDEO_SAMPLE_CHUNK_DURATION_S': S3_PRE_SIGNED_URL_EXPIRY_S,
                'VIDEO_SAMPLE_S3_PREFIX': VIDEO_SAMPLE_S3_PREFIX,
                'VIDEO_SAMPLE_S3_BUCKET': self.s3_bucket_name_mm,
            }, 
            timeout_s=900, memory_size=3008, ephemeral_storage_size=10240,
            layers=[self.moviepy_layer],
        )

    def deploy_apigw_lambda(self):
        # API Gateway - start
        api = _apigw.RestApi(self, f"{API_NAME_PREFIX}",
                                rest_api_name=f"{API_NAME_PREFIX}",
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
        tlabs = v1.add_resource("tlabs")
        embed = tlabs.add_resource("embedding")
        
        self.api_gw_base_url = api.url
                                     
        # POST v1/embedding/delete-task
        # Lambda: tlabs-srv-delete-video-task
        lambda_key = "tlabs-srv-delete-video-task" 
        lambda_role = self.create_role(lambda_key, ["s3","dynamodb","s3vectors"])

        self.create_api_endpoint(id='TLabsLambdaDeleteTaskEp', 
            root=embed, path1="delete-task", method="POST", auth=self.cognito_authorizer, 
            role=lambda_role, 
            lambda_file_name=lambda_key, 
            instance_hash=self.instance_hash, memory_m=1024, timeout_s=30, ephemeral_storage_size=512,
            evns={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'TLABS_S3_VECTOR_BUCKET': S3_VECTOR_BUCKET_TLABS,
                'TLABS_S3_VECTOR_INDEX': S3_VECTOR_INDEX_TLABS,
            },
            layers=[self.boto3_layer]
        )   

        # POST /v1/embedding/get-task-clips
        # Lambda: tlabs-srv-get-task-clips
        lambda_key = "tlabs-srv-get-task-clips" 
        lambda_role = self.create_role(lambda_key, ["s3","dynamodb"])
        self.create_api_endpoint(id='TLabsLambdaGetTaskClipsEp', root=embed, path1="get-task-clips", method="POST", auth=self.cognito_authorizer, 
                role=lambda_role, 
                lambda_file_name=lambda_key,
                instance_hash=self.instance_hash, memory_m=1024, timeout_s=30, ephemeral_storage_size=512,
            evns={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
            })        
        
        # POST /v1/embedding/tlabs-search-vector
        # Lambda: tlabs-srv-search-vector
        lambda_key = "tlabs-srv-search-vector" 
        lambda_role = self.create_role(lambda_key, ["s3","dynamodb","s3vectors","dynamodb", "bedrock"])
        self.create_api_endpoint(id='TLabsLambdaSearchVectorEp', root=embed, path1="search-task-vector", method="POST", auth=self.cognito_authorizer, 
                role=lambda_role, 
                lambda_file_name=lambda_key,
                instance_hash=self.instance_hash, memory_m=1024, timeout_s=180, ephemeral_storage_size=1024,
            evns={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'S3_PRE_SIGNED_URL_EXPIRY_S': S3_PRE_SIGNED_URL_EXPIRY_S,
                'TLABS_S3_VECTOR_BUCKET': S3_VECTOR_BUCKET_TLABS,
                'TLABS_S3_VECTOR_INDEX':S3_VECTOR_INDEX_TLABS,
                'S3_BUCKET_DATA': self.s3_bucket_name_mm
            },
            layers=[self.boto3_layer]
            )   

        # POST /v1/embedding/start-task
        # Lambda: tlabs-srv-start-task
        lambda_key = "tlabs-srv-start-task" 
        lambda_role = self.create_role(lambda_key, ["s3","dynamodb","dynamodb", "bedrock", "lambda"])
        self.create_api_endpoint(id='TLabsLambdaStartTaskEp', root=embed, path1="start-task", method="POST", auth=self.cognito_authorizer, 
                role=lambda_role, 
                lambda_file_name=lambda_key,
                instance_hash=self.instance_hash, memory_m=128, timeout_s=30, ephemeral_storage_size=512,
            evns={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'AWS_ACCOUNT_ID':self.account_id,
                'LAMBDA_FUN_NAME_VIDEO_METADATA': self.lambda_tlabs_get_video_metadata.function_name
            })      

        # POST /v1/tlabs/embedding/get-task
        # Lambda: tlabs-srv-get-video-task
        lambda_key = "tlabs-srv-get-video-task" 
        lambda_role = self.create_role(lambda_key, ["s3","dynamodb"])
        self.create_api_endpoint(id='TlabsSrvGetTaskEp', root=embed, path1="get-task", method="POST", auth=self.cognito_authorizer, 
                role=lambda_role, 
                lambda_file_name=lambda_key,
                instance_hash=self.instance_hash, memory_m=128, timeout_s=20, ephemeral_storage_size=1024,
            evns={
                'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                'S3_PRESIGNED_URL_EXPIRY_S':S3_PRE_SIGNED_URL_EXPIRY_S,
            })           
        
        # POST /v1/tlabs/embedding/search-task
        # Lambda: tlabs-srv-get-video-tasks 
        lambda_key = "tlabs-srv-get-video-tasks" 
        lambda_role = self.create_role(lambda_key, ["s3","dynamodb"])
        self.create_api_endpoint(id='TlabsSrvGetTasksEp', root=embed, path1="search-task", method="POST", auth=self.cognito_authorizer, 
                role=lambda_role,
                lambda_file_name=lambda_key,
                instance_hash=self.instance_hash, memory_m=128, timeout_s=10, ephemeral_storage_size=1024,
                evns={
                    'DYNAMO_VIDEO_TASK_TABLE': DYNAMO_VIDEO_TASK_TABLE,
                    'DYNAMO_VIDEO_TRANS_TABLE': "",
                    'DYNAMO_VIDEO_FRAME_TABLE': "",
                    'S3_PRE_SIGNED_URL_EXPIRY_S': S3_PRE_SIGNED_URL_EXPIRY_S,
                }
        )


        util = v1.add_resource("util")

        # POST /v1/util/manage-s3-presigned-url
        # Lambda: tlabs-srv-util-manage-s3-presigned-url
        lambda_key = "tlabs-srv-util-manage-s3-presigned-url" 
        lambda_role = self.create_role(lambda_key, ["s3"])
        self.create_api_endpoint(id='UtilManageS3UrlEp', root=util, path1="manage-s3-presigned-url", method="POST", auth=self.cognito_authorizer, 
                role=lambda_role,
                lambda_file_name=lambda_key,
                instance_hash=self.instance_hash, memory_m=128, timeout_s=10, ephemeral_storage_size=512,
                evns={
                    'S3_PRESIGNED_URL_EXPIRY_S': S3_PRE_SIGNED_URL_EXPIRY_S,
                    'VIDEO_UPLOAD_S3_PREFIX': VIDEO_UPLOAD_S3_PREFIX,
                    'VIDEO_UPLOAD_S3_BUCKET': self.s3_bucket_name_mm
                }
            )   

    def create_api_endpoint(self, id, root, path1, method, auth, role, lambda_file_name, instance_hash, memory_m, timeout_s, ephemeral_storage_size, evns, layers=None):
        lambda_function = _lambda.Function(self, 
            id=id, 
            function_name=f"{LAMBDA_NAME_PREFIX}{lambda_file_name}", 
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler=f'{lambda_file_name}.lambda_handler',
            code=_lambda.Code.from_asset(os.path.join("../source/", f"tlabs_service/lambda/{lambda_file_name}")),
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

    def create_role(self, function_name, policies):
        statements=[
            _iam.PolicyStatement(
                effect=_iam.Effect.ALLOW,
                actions=["logs:CreateLogGroup"],
                resources=[f"arn:aws:logs:{self.region}:{self.account_id}:*"]
            ),
            _iam.PolicyStatement(
                effect=_iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/lambda/{LAMBDA_NAME_PREFIX}{function_name}:*"]
            )
        ]
        if "s3" in policies:
            statements.append(
                _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3:ListBucket","s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListBucketMultipartUploads"],
                        resources=[f"arn:aws:s3:::{self.s3_bucket_name_mm}",f"arn:aws:s3:::{self.s3_bucket_name_mm}/*"]
                    )
            )
        if "dynamodb" in policies:
            statements.append(
                _iam.PolicyStatement(
                        actions=["dynamodb:DeleteItem","dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem","dynamodb:DescribeTable","dynamodb:BatchWriteItem"],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}/index/*",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{DYNAMO_VIDEO_TASK_TABLE}",
                        ]
                    ))
        if "bedrock" in policies:
            statements.append(
                _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["bedrock:InvokeModel","bedrock:GetAsyncInvoke"],
                        resources=[
                            "arn:aws:bedrock:*:*:foundation-model/*",
                            "arn:aws:bedrock:*:*:async-invoke/*",
                            "arn:aws:bedrock:*:*:inference-profile/*"
                        ]
                    )
            )
        if "s3vectors" in policies:
            statements.append(
                _iam.PolicyStatement(
                        effect=_iam.Effect.ALLOW,
                        actions=["s3vectors:*"],
                        resources=[f"arn:aws:s3vectors:{self.region}:{self.account_id}:bucket/{S3_VECTOR_BUCKET_TLABS}*"]
                    )
            )
        if "lambda" in policies:
            statements.append(
                 _iam.PolicyStatement(
                    effect=_iam.Effect.ALLOW,
                    actions=["lambda:InvokeFunction"],
                    resources=[
                        f"arn:aws:lambda:{self.region}:{self.account_id}:function:{LAMBDA_NAME_PREFIX}tlabs-srv*"
                    ]
                ),
            )
        if "events" in policies:
            statements.append(
                _iam.PolicyStatement(
                    effect=_iam.Effect.ALLOW,
                    actions=["events:PutEvents"],
                    resources=[f"arn:aws:events:{self.region}:{self.account_id}:event-bus/*"]
                )
            )

        return _iam.Role(
            self, f"{self.to_pascal(function_name)}Role",
            assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={f"{function_name}-poliy": _iam.PolicyDocument(
            statements=statements
        )}
    )   

    def create_lambda(self, function_name, role, environment, timeout_s=30, memory_size=128, ephemeral_storage_size=512, layers=[]):
        return _lambda.Function(self, 
            id=f'{self.to_pascal(function_name)}Lambda', 
            function_name=f'{LAMBDA_NAME_PREFIX}{function_name}', 
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler=f'{function_name}.lambda_handler',
            code=_lambda.Code.from_asset(os.path.join("../source/", f"tlabs_service/lambda/{function_name}")),
            timeout=Duration.seconds(timeout_s),
            memory_size=memory_size,
            ephemeral_storage_size=Size.mebibytes(ephemeral_storage_size),
            role=role,
            environment=environment,
            layers=layers,
        )

    def to_pascal(self,s: str) -> str:
        # Split on non-alphanumeric characters and underscores
        words = re.split(r'[^a-zA-Z0-9]', s)
        # Capitalize each word and join
        return ''.join(word.capitalize() for word in words if word)