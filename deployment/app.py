#!/usr/bin/env python3
import aws_cdk as cdk
from aws_cdk import CfnParameter as _cfnParameter
from aws_cdk import Stack,CfnOutput
from aws_cdk import Duration

import os, json
from nova_service.nova_service_stack import NovaServiceStack
from pre_stack.service_pre_stack import ServicePreStack
from post_stack.service_post_stack import ServicePostStack
from extraction_service.extraction_service_stack import ExtrServiceStack
from tlabs_service.tlabs_service_stack import TlabsServiceStack
from frontend.frontend_stack import FrontendStack
from analytics.analytics_stack import AnalyticsStack
from agent_stack.agent_stack import AgentStack
from cdk_nag import AwsSolutionsChecks, NagSuppressions
import secrets
import string
import random
from extraction_service.constant import *

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"), 
    region=os.environ.get("CDK_DEFAULT_REGION")
)

def generate_password():
    min_length = 8
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = string.punctuation

    # ensure at least one from each required category
    required = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]

    # build pool of all allowed characters
    all_chars = lowercase + uppercase + digits + symbols

    # fill remaining characters to meet min_length
    remaining = [secrets.choice(all_chars) for _ in range(min_length - len(required))]
    password_chars = required + remaining

    # shuffle for randomness
    random.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)

class RootStack(Stack):
    user_emails = None
    user_name = None
    password = None

    def __init__(self, scope):
        super().__init__(scope, id="BedrockMmRootStack", env=env, description="Nova MME stack.",
        )

        # Inputs
        input_user_emails = _cfnParameter(self, "inputUserEmails", type="String",
                                    description="Use your email to log in to the web portal. Split by comma if there are multiple emails.",
                                    default=""
                                )
        input_user_name = _cfnParameter(self, "inputUserName", type="String",
                                    description="Provide a username to bypass Cognito's email authentication; the user is created with a random password and no email/reset required — suitable for workshops.",
                                    default=""
                                )
        
        if input_user_emails:
            self.user_emails = input_user_emails.value_as_string
        if input_user_name:
            self.user_name = input_user_name.value_as_string
            if self.user_name:
                self.password = generate_password()
        
        # Preperation stack
        srv_pre_stack = ServicePreStack(self, 
            "ExtractionServicePreStack", 
            description="Deploy S3 data bucket, Cognito user pool, build Lambda Layers, deploy S3 vector bucket and index.",
            timeout = Duration.hours(1)
        )

        # Extraction Service Stack
        extr_service_stack = ExtrServiceStack(self, 
            "ExtractionServiceStack", 
            description="Deploy Extraction service backend services: DynamoDB, API Gateway, Lambda, StepFunctions, etc.",
            timeout = Duration.hours(4),
            s3_bucket_name_extraction = srv_pre_stack.s3_data_bucket_name,
            cognito_user_pool_id=srv_pre_stack.cognito_user_pool_id,
            cognito_app_client_id=srv_pre_stack.cognito_app_client_id
        )
        extr_service_stack.node.add_dependency(srv_pre_stack)

        # Nova service stack
        nova_service_stack = NovaServiceStack(self, 
            "NovaServiceStack", 
            description="Deploy Nova backend services: DynamoDB, API Gateway, Lambda, etc.",
            timeout = Duration.hours(4),
            s3_bucket_name_mm = srv_pre_stack.s3_data_bucket_name,
            cognito_user_pool_id=srv_pre_stack.cognito_user_pool_id,
            cognito_app_client_id=srv_pre_stack.cognito_app_client_id
        )
        nova_service_stack.node.add_dependency(srv_pre_stack)

        #Tlabs service stack
        tlabs_service_stack = TlabsServiceStack(self, 
            "TlabsServiceStack",
            description="Deploy Tlabs MME backend services: DynamoDB, API Gateway, Lambda, etc.",
            timeout = Duration.hours(4),
            s3_bucket_name_mm = srv_pre_stack.s3_data_bucket_name,
            cognito_user_pool_id=srv_pre_stack.cognito_user_pool_id,
            cognito_app_client_id=srv_pre_stack.cognito_app_client_id
        )
        tlabs_service_stack.node.add_dependency(srv_pre_stack)

        # Analytics stack (conditional deployment)
        analytics_stack = AnalyticsStack(self,  
            "AnalyticsStack", 
            s3_bucket_name_data_str = f'{S3_BUCKET_DATA_PREFIX}-{os.environ.get("CDK_DEFAULT_ACCOUNT")}-{os.environ.get("CDK_DEFAULT_REGION")}'
        )
        analytics_stack.node.add_dependency(srv_pre_stack)

        # Agent stack
        # agent_stack = AgentStack(self,  
        #     "AgentStack", 
        # )

        # Frontend stack
        frontend_stack = FrontendStack(self, 
            "FrontStack", 
            description="Deploy frontend static website: S3, CloudFormation",
            api_gw_base_url_nova_srv = nova_service_stack.api_gw_base_url,
            api_gw_base_url_extr_srv = extr_service_stack.api_gw_base_url,
            api_gw_base_url_tlabs_srv = tlabs_service_stack.api_gw_base_url,
            cognito_user_pool_id = srv_pre_stack.cognito_user_pool_id,
            cognito_app_client_id = srv_pre_stack.cognito_app_client_id,
            cognito_identity_pool_id = srv_pre_stack.cognito_identity_pool_id,
            s3_bucket_name_data = srv_pre_stack.s3_data_bucket_name,
            agentcore_runtime_arn = ""#agent_stack.agentcore_runtime_arn
        )
        frontend_stack.node.add_dependency(nova_service_stack)
        frontend_stack.node.add_dependency(extr_service_stack)
        frontend_stack.node.add_dependency(tlabs_service_stack)
        if analytics_stack:
            frontend_stack.node.add_dependency(analytics_stack)
        #frontend_stack.node.add_dependency(agent_stack)

        # Service post stack
        service_post_stack = ServicePostStack(self, 
            "ServicePostStack", 
            description="Create Cognito user, send invitation email",
            s3_web_bucket_name = frontend_stack.s3_web_bucket_name,
            s3_data_bucket_name = srv_pre_stack.s3_data_bucket_name,
            cloudfront_url = frontend_stack.output_url,
            cognito_user_pool_id = srv_pre_stack.cognito_user_pool_id,
            cognito_app_client_id = srv_pre_stack.cognito_app_client_id,
            user_emails = self.user_emails,
            cognito_user_name = self.user_name,
            cognito_user_pwd = self.password
        )
        service_post_stack.node.add_dependency(frontend_stack)

        CfnOutput(self, "Website URL", value=f"https://{frontend_stack.output_url}")

        CfnOutput(self, "API Gateway Base URL: Extraction Service (frame and clip baed workflow)", value=extr_service_stack.api_gw_base_url)
        CfnOutput(self, "API Gateway Base URL: Nova MME Service", value=nova_service_stack.api_gw_base_url)
        CfnOutput(self, "API Gateway Base URL: TLabs MME Service", value=tlabs_service_stack.api_gw_base_url)
        
        CfnOutput(self, "Cognito User Pool Id", value=extr_service_stack.cognito_user_pool_id)
        CfnOutput(self, "Cognito App Client Id", value=extr_service_stack.cognito_app_client_id)
        CfnOutput(self, "Cognito Identity Pool Id", value=srv_pre_stack.cognito_identity_pool_id)

        if self.user_name and self.password:
            CfnOutput(self, "Cognito User Name", value=self.user_name)
            CfnOutput(self, "Cognito User Password", value=self.password)

        #CfnOutput(self, "AgentCore Runtime Arn", value=agent_stack.agentcore_runtime_arn)
        
        # Analytics deployment status
        CfnOutput(self, "Analytics Deployed", 
                 value="true" if analytics_stack else "false",
                 description="Whether the analytics stack with SageMaker notebook is deployed")

app = cdk.App()
root_stack = RootStack(app)

nag_suppressions = [
        {
            "id": "AwsSolutions-IAM5",
            "reason": "AWS managed policies are allowed which sometimes use wildcards (*) in resources - for example, Transcribe services require broad permissions. IAM policies using wildcards are implemented with proper prefixes to minimize the risk of accessing resources outside of this solution's scope.",
        },
        {
            "id": "AwsSolutions-IAM4",
            "reason": "AWS Managed IAM policies have been allowed to maintain secured access with the ease of operational maintenance - however for more granular control the custom IAM policies can be used instead of AWS managed policies",
        },
        {
            'id': 'AwsSolutions-APIG2',
            'reason': 'API request validation is handled within the Lambda functions.'
        },
        {
            'id': 'AwsSolutions-APIG4',
            'reason': 'False Positive detection. All API Gateway methods are authorized using a Cognitio authrozier provisioned in the CDK.'
        },
        {
            'id': 'AwsSolutions-COG4',
            'reason': 'False Positive detection. All API Gateway methods are authorized using a Cognitio authrozier provisioned in the CDK.'
        },
        {
            'id': 'AwsSolutions-S1',
            'reason': 'The CloudFront access log bucket has logging disabled. It is up to the user to decide whether to enable the access log to the log bucket.'
        },
        {
            'id': 'AwsSolutions-CFR4',
            'reason': 'The internal admin web portal is deployed using the default CloudFront domain and certification. User can set up DNS to route the web portal through their managed domain and replace the certification to resolve this issue.'
        },
        {
            'id': 'AwsSolutions-COG3',
            'reason': 'The Cognito user pool is used for an admin web UI authentication and does not allow public registration. Enabling AdvancedSecurityMode is optional and left to the users discretion.'
        },
        {
            'id': 'AwsSolutions-CFR7',
            'reason': 'False positive. The CloudFromation distribution has enbaled OAI access to the S3 origin.'
        },
        {
            'id': 'AwsSolutions-L1',
            'reason': 'False positive. There is no Lambda deployment in the analytics stack.'
        },
        {
            'id': 'AwsSolutions-CB4',
            'reason': 'The target s3 bucket is for public web hosting which does not require encryption.'
        },
        {
            'id': 'AwsSolutions-SM1',
            'reason': 'The analysis stack, which includes the SageMaker notebook deployment, is available for workshop and disabled by default. It runs in a temporary environment.'
        },
        {
            'id': 'AwsSolutions-SM3',
            'reason': 'The analysis stack, which includes the SageMaker notebook deployment, is available for workshop and disabled by default. It runs in a temporary environment.'
        },
    ]

NagSuppressions.add_stack_suppressions(
    root_stack,
    nag_suppressions,
    apply_to_nested_stacks=True
)

cdk.Aspects.of(app).add(AwsSolutionsChecks())

app.synth()
