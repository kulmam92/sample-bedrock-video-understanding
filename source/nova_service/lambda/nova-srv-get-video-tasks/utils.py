import boto3
import numbers,decimal
from boto3.dynamodb.types import TypeDeserializer
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')

def dynamodb_table_upsert(table_name, document):
    try:
        document = convert_to_json_serializable(document)
        table = dynamodb.Table(table_name)
        return table.put_item(Item=document)
    except Exception as e:
        print(f"An error occurred, dynamodb_table_upsert: {e}")
        return None
    
def dynamodb_get_by_id(table_name, id, key_name="Id", sort_key_value=None, sort_key=None):
    try:
        table = dynamodb.Table(table_name)
        response = None
        if sort_key and sort_key_value:
            response = table.get_item(Key={key_name: sort_key_value, sort_key: sort_key})
        else:
            response = table.get_item(Key={key_name: id})
        if 'Item' in response:
            return convert_to_json_serializable(response['Item'])
        else:
            print(f"No item found with id: {document_id}")
            return None
    except Exception as e:
        print(f"An error occurred, dynamodb_get_by_id: {e}")
        return None
    return None

def dynamodb_delete_by_id(table_name, id):
    try:
        response = dynamodb_client.delete_item(
            TableName=table_name,
            Key=id
        )
        print(f"Item with key {key} deleted successfully from table '{table_name}'.")
    except Exception as e:
        print(f"Error deleting item with key {key} from table {table_name}: {str(e)}")


def convert_to_json_serializable(item):
    """
    Recursively convert a DynamoDB item to a JSON serializable format.
    """
    if isinstance(item, dict):
        return {k: convert_to_json_serializable(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [convert_to_json_serializable(v) for v in item]
    elif isinstance(item, float):
        return str(item)
    elif isinstance(item, decimal.Decimal):
        return str(item)
    else:
        return item

def dynamodb_task_update_status(table_name, task_id, new_status):    
    try:
        response = dynamodb.update_item(
            TableName=table_name,
            Key={
                'Id': {'S': task_id}
            },
            UpdateExpression="SET #status = :new_status",
            ExpressionAttributeNames={
                '#status': 'Status'
            },
            ExpressionAttributeValues={
                ':new_status': {'S': new_status}
            },
            ReturnValues="UPDATED_NEW"
        )
        print(f"Update succeeded: {response}")
    except Exception as e:
        print(f"Error updating item in table {table_name}: {str(e)}")

def count_items_by_task_id(table_name, task_id):
    table = dynamodb.Table(table_name)
    response = table.query(
        IndexName='task_id-timestamp-index', 
        KeyConditionExpression=Key('task_id').eq(task_id), 
        Select='COUNT'
    )
    return response['Count']

import boto3

def query_task_with_pagination(table_name, request_by, keyword, start_index=0, page_size=10):
    table = dynamodb.Table(table_name)

    # Query operation parameters
    query_kwargs = {
        'IndexName': 'RequestBy-index', 
        'KeyConditionExpression': 'RequestBy = :request_by',
        'ExpressionAttributeValues': {
            ':request_by': request_by
        }
    }

    # Initialize variables for pagination
    items = []
    pagination_token = None

    while True:
        if pagination_token:
            query_kwargs['ExclusiveStartKey'] = pagination_token

        response = table.query(**query_kwargs)
        # Filter items where file_name contains the keyword
        keyword = keyword.lower()
        filtered_items = [item for item in response['Items'] if keyword in item["Request"]["FileName"].lower()]
        items.extend(filtered_items)

        if 'LastEvaluatedKey' in response:
            pagination_token = response['LastEvaluatedKey']
        else:
            break

    # Handle manual pagination
    end_index = start_index + page_size
    paginated_items = items[start_index:end_index]

    return paginated_items

def scan_task_with_pagination(table_name, keyword, start_index=0, page_size=10):
    """
    Scan a DynamoDB table for tasks where 'FileName' or 'TaskName' contains a keyword.
    Supports manual pagination.

    Args:
        table_name (str): Name of the DynamoDB table.
        keyword (str): Keyword to search in FileName or TaskName (case-insensitive).
        start_index (int, optional): Start index for manual pagination. Defaults to 0.
        page_size (int, optional): Number of items to return per page. Defaults to 10.

    Returns:
        list[dict]: Paginated list of matching items.
    """
    table = dynamodb.Table(table_name)

    items = []
    scan_kwargs = {}  # Add any scan filters if needed in future
    pagination_token = None

    while True:
        if pagination_token:
            scan_kwargs['ExclusiveStartKey'] = pagination_token

        response = table.scan(**scan_kwargs)

        # Filter items by keyword in FileName or TaskName
        keyword_lower = keyword.lower()
        filtered_items = [
            item for item in response.get('Items', [])
            if keyword_lower in item.get("Request", {}).get("FileName", "").lower()
            or keyword_lower in item.get("Request", {}).get("TaskName", "").lower()
        ]
        items.extend(filtered_items)

        # Continue scanning if more items exist
        pagination_token = response.get('LastEvaluatedKey')
        if not pagination_token:
            break

    # Manual pagination
    end_index = start_index + page_size
    paginated_items = items[start_index:end_index]

    return paginated_items