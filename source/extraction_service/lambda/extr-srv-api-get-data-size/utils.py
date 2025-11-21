import boto3
import decimal
import json
from boto3.dynamodb.conditions import Key, Attr

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

def calculate_s3_prefix_size(bucket_name, prefix):
    """
    Calculate the total size and file count for objects under a specific S3 prefix.
    
    Parameters:
    - bucket_name: Name of the S3 bucket
    - prefix: S3 prefix to calculate size for
    
    Returns:
    - Dictionary with size, file_count, and max_file_size
    """
    try:
        total_size = 0
        file_count = 0
        max_file_size = 0
        
        # Use paginator to handle large number of objects
        paginator = s3.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # Skip directories (objects ending with '/')
                    if not obj['Key'].endswith('/'):
                        size = obj['Size']
                        total_size += size
                        file_count += 1
                        max_file_size = max(max_file_size, size)
        
        return {
            'size': total_size,
            'file_count': file_count,
            'max_file_size': max_file_size
        }
        
    except Exception as e:
        print(f"Error calculating S3 prefix size for {prefix}: {str(e)}")
        return {
            'size': 0,
            'file_count': 0,
            'max_file_size': 0
        }

def calculate_dynamodb_task_size(table_name, task_id):
    """
    Calculate the estimated size of DynamoDB records for a specific task.
    
    Parameters:
    - table_name: Name of the DynamoDB table
    - task_id: Task ID to filter records
    
    Returns:
    - Dictionary with estimated_size, record_count, and max_record_size
    """
    try:
        table = dynamodb.Table(table_name)
        total_size = 0
        record_count = 0
        max_record_size = 0
        
        if table_name.endswith('_video_task'):
            # Task table uses 'Id' as primary key
            response = table.get_item(Key={'Id': task_id})
            if 'Item' in response:
                item_size = estimate_item_size(response['Item'])
                total_size += item_size
                record_count = 1
                max_record_size = item_size
        else:
            # Other tables have task_id-*-index GSI
            last_evaluated_key = None
            while True:
                query_params = {
                    'IndexName': 'task_id-timestamp-index' if 'frame' in table_name else 
                                 'task_id-start_ts-index' if 'transcript' in table_name else
                                 'task_id-analysis_type-index',
                    'KeyConditionExpression': Key('task_id').eq(task_id)
                }
                if last_evaluated_key:
                    query_params['ExclusiveStartKey'] = last_evaluated_key
                
                response = table.query(**query_params)
                
                for item in response.get('Items', []):
                    item_size = estimate_item_size(item)
                    total_size += item_size
                    record_count += 1
                    max_record_size = max(max_record_size, item_size)
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
        
        return {
            'estimated_size': total_size,
            'record_count': record_count,
            'max_record_size': max_record_size
        }
        
    except Exception as e:
        print(f"Error calculating DynamoDB size for {table_name}: {str(e)}")
        return {
            'estimated_size': 0,
            'record_count': 0,
            'max_record_size': 0
        }

def estimate_item_size(item):
    """
    Estimate the size of a DynamoDB item in bytes.
    
    Parameters:
    - item: DynamoDB item
    
    Returns:
    - Estimated size in bytes
    """
    try:
        # Convert to JSON string and calculate byte size
        json_str = json.dumps(item, default=str)
        return len(json_str.encode('utf-8'))
    except Exception:
        return 0

def convert_to_json_serializable(item):
    """
    Recursively convert a DynamoDB item to a JSON serializable format.
    Handles Decimal types from DynamoDB.
    """
    if isinstance(item, dict):
        return {k: convert_to_json_serializable(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [convert_to_json_serializable(v) for v in item]
    elif isinstance(item, float):
        return str(item)
    elif isinstance(item, decimal.Decimal):
        # Convert Decimal to int if it's a whole number, otherwise to float
        if item % 1 == 0:
            return int(item)
        else:
            return float(item)
    else:
        return item