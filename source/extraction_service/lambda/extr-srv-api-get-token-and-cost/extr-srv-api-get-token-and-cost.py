import json
import boto3
import os
import utils
from decimal import Decimal

DYNAMO_VIDEO_USAGE_TABLE = os.environ.get("DYNAMO_VIDEO_USAGE_TABLE")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    """
    Lambda function to retrieve token usage and cost information from DynamoDB.
    
    Parameters:
    - task_id: Required. The task ID to query usage data for.
    - type: Optional. Filter by usage type (e.g., 'nova_mme_video', 'image_understanding').
    - region: Optional. AWS region for pricing (defaults to Lambda's region).
    
    Returns:
    - statusCode: 200 on success, 400 on error
    - body: List of usage records or error message
    """
    task_id = event.get("task_id") or event.get("TaskId")
    usage_type = event.get("type") or event.get("Type")
    region = event.get("region") or event.get("Region") or AWS_REGION
    
    if not task_id:
        return {
            'statusCode': 400,
            'body': {
                'error': 'Invalid request. Missing task_id parameter.'
            }
        }
    
    try:
        # Query usage data from DynamoDB
        usage_records = utils.query_usage_by_task_id(
            table_name=DYNAMO_VIDEO_USAGE_TABLE,
            task_id=task_id,
            usage_type=usage_type
        )
        
        if not usage_records:
            return {
                'statusCode': 200,
                'body': {
                    'task_id': task_id,
                    'region': region,
                    'usage_records': [],
                    'summary': {
                        'total_records': 0,
                        'total_input_tokens': 0,
                        'total_output_tokens': 0,
                        'total_tokens': 0,
                        'total_cost_usd': 0.0
                    }
                }
            }
        
        # Convert Decimal types to JSON serializable format
        usage_records = utils.convert_to_json_serializable(usage_records)
        
        return {
            'statusCode': 200,
            'body': {
                'task_id': task_id,
                'region': region,
                'usage_records': usage_records,
            }
        }
        
    except Exception as e:
        print(f"Error retrieving usage data: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'error': f'Error retrieving usage data: {str(e)}'
            }
        }
