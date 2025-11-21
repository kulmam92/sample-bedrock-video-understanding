import json
import boto3
import os
import utils
from decimal import Decimal

S3_BUCKET = os.environ.get("S3_BUCKET")
DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
DYNAMO_VIDEO_FRAME_TABLE = os.environ.get("DYNAMO_VIDEO_FRAME_TABLE")
DYNAMO_VIDEO_SHOT_TABLE = os.environ.get("DYNAMO_VIDEO_SHOT_TABLE")
DYNAMO_VIDEO_TRANS_TABLE = os.environ.get("DYNAMO_VIDEO_TRANS_TABLE")
DYNAMO_VIDEO_USAGE_TABLE = os.environ.get("DYNAMO_VIDEO_USAGE_TABLE")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    """
    Lambda function to calculate data size information for a video processing task.
    
    Parameters:
    - task_id: Required. The task ID to calculate data sizes for.
    
    Returns:
    - statusCode: 200 on success, 400 on error
    - body: Data size breakdown or error message
    """
    task_id = event.get("task_id") or event.get("TaskId")
    
    if not task_id:
        return {
            'statusCode': 400,
            'body': {
                'error': 'Invalid request. Missing task_id parameter.'
            }
        }
    
    if not S3_BUCKET:
        return {
            'statusCode': 500,
            'body': {
                'error': 'S3 bucket configuration missing.'
            }
        }
    
    try:
        # Calculate data sizes for different data types
        data_breakdown = {}
        total_size = 0
        total_files = 0
        
        # S3 data types and their prefixes
        s3_data_types = {
            'video_frame': f'tasks/{task_id}/video_frame_/',
            'frame_outputs': f'tasks/{task_id}/frame_outputs/',
            'frame_analysis': f'tasks/{task_id}/frame_analysis/',
            'shot_clip': f'tasks/{task_id}/shot_clip/',
            'shot_outputs': f'tasks/{task_id}/shot_outputs/',
            'shot_vector': f'tasks/{task_id}/shot_vector/',
            'transcribe': f'tasks/{task_id}/transcribe/'
        }
        
        # Calculate S3 data sizes
        for data_type, prefix in s3_data_types.items():
            try:
                size_info = utils.calculate_s3_prefix_size(S3_BUCKET, prefix)
                if size_info['file_count'] > 0:  # Only include if files exist
                    data_breakdown[data_type] = size_info
                    total_size += size_info['size']
                    total_files += size_info['file_count']
            except Exception as e:
                print(f"Error calculating S3 size for {data_type}: {str(e)}")
                continue
        
        # Calculate DynamoDB data sizes
        dynamodb_tables = {
            'task_metadata': DYNAMO_VIDEO_TASK_TABLE,
            'frame_analysis': DYNAMO_VIDEO_FRAME_TABLE,
            'shot_analysis': DYNAMO_VIDEO_SHOT_TABLE,
            'transcription': DYNAMO_VIDEO_TRANS_TABLE,
            'usage_tracking': DYNAMO_VIDEO_USAGE_TABLE
        }
        
        for data_type, table_name in dynamodb_tables.items():
            try:
                size_info = utils.calculate_dynamodb_task_size(table_name, task_id)
                if size_info['record_count'] > 0:  # Only include if records exist
                    data_breakdown[f'dynamodb_{data_type}'] = {
                        'size': size_info['estimated_size'],
                        'file_count': size_info['record_count'],
                        'max_file_size': size_info['max_record_size']
                    }
                    total_size += size_info['estimated_size']
                    total_files += size_info['record_count']
            except Exception as e:
                print(f"Error calculating DynamoDB size for {data_type}: {str(e)}")
                continue
        
        return {
            'statusCode': 200,
            'body': {
                'task_id': task_id,
                'total_size': total_size,
                'total_files': total_files,
                'data_breakdown': data_breakdown,
                'bucket': S3_BUCKET,
                'region': AWS_REGION
            }
        }
        
    except Exception as e:
        print(f"Error calculating data sizes: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'error': f'Error calculating data sizes: {str(e)}'
            }
        }