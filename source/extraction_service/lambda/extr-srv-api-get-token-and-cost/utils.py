import boto3
import decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')


def query_usage_by_task_id(table_name, task_id, usage_type=None):
    """
    Query usage records from DynamoDB by task_id and optionally filter by type using GSI.
    
    Parameters:
    - table_name: Name of the DynamoDB table
    - task_id: The task ID to query
    - usage_type: Optional type filter (e.g., 'nova_mme_video', 'image_understanding')
    
    Returns:
    - List of usage records
    """
    try:
        table = dynamodb.Table(table_name)
        items = []
        last_evaluated_key = None
        
        # Query parameters using the task_id-type-index GSI
        query_params = {
            'IndexName': 'task_id-type-index',
        }
        
        # If type is provided, use it as part of the key condition
        if usage_type:
            query_params['KeyConditionExpression'] = Key('task_id').eq(task_id) & Key('type').eq(usage_type)
        else:
            # If no type filter, just query by task_id
            query_params['KeyConditionExpression'] = Key('task_id').eq(task_id)
        
        # Paginate through all results
        while True:
            if last_evaluated_key:
                query_params['ExclusiveStartKey'] = last_evaluated_key
            
            response = table.query(**query_params)
            items.extend(response.get('Items', []))
            
            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
        
        return items
        
    except Exception as e:
        print(f"Error querying usage data: {str(e)}")
        raise


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


def dynamodb_table_upsert(table_name, document):
    """
    Insert or update a document in DynamoDB table.
    
    Parameters:
    - table_name: Name of the DynamoDB table
    - document: Dictionary containing the item to upsert
    
    Returns:
    - Response from DynamoDB or None on error
    """
    try:
        document = convert_to_json_serializable(document)
        table = dynamodb.Table(table_name)
        return table.put_item(Item=document)
    except Exception as e:
        print(f"An error occurred, dynamodb_table_upsert: {e}")
        return None
