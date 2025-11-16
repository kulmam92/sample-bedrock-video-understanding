import json
import boto3
import os
import utils

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
TLABS_S3_VECTOR_BUCKET = os.environ.get("TLABS_S3_VECTOR_BUCKET")
TLABS_S3_VECTOR_INDEX_27 = os.environ.get("TLABS_S3_VECTOR_INDEX_27")
TLABS_S3_VECTOR_INDEX_30 = os.environ.get("TLABS_S3_VECTOR_INDEX_30")

TLABS_OUTPUT_KEY_PREFIX_TEMPLATE = "tasks/{task_id}/tlabs/"
S3_KEY_PREFIX_TEMPLATE = "tasks/{task_id}/"

s3 = boto3.client('s3')
s3vectors = boto3.client('s3vectors') 

def lambda_handler(event, context):
    task_id = event.get("TaskId")
    delete_s3 = event.get("DeleteS3", True)
    if task_id is None:
        return {
            'statusCode': 400,
            'body': json.dumps('Require TaskId')
        }
    
    # Get video task from DB
    task = None
    try:
        task = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    except Exception as ex:
        print(f'Task does not exist in {DYNAMO_VIDEO_TASK_TABLE}: {task_id}')

    s3_bucket = task["Request"]["Video"]["S3Object"]["Bucket"]

    task_type = task.get("Request",{}).get("TaskType")
    TLABS_S3_VECTOR_INDEX = TLABS_S3_VECTOR_INDEX_27 if task_type == "marengo27" else TLABS_S3_VECTOR_INDEX_30

    # Delete S3 vectors
    delete_s3_vectors(s3_bucket, 
        TLABS_OUTPUT_KEY_PREFIX_TEMPLATE.format(task_id=task_id), 
        TLABS_S3_VECTOR_BUCKET, 
        TLABS_S3_VECTOR_INDEX, 
        task_id
    )

    # Delete S3 task folder
    delete_s3_folder(s3_bucket, S3_KEY_PREFIX_TEMPLATE.format(task_id=task_id))

    # Delete from DynamoDB task table
    try:
        utils.dynamodb_delete_task_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    except Exception as ex:
        print(f'Failed to delete task {task_id} from index: {DYNAMO_VIDEO_TASK_TABLE}', ex)

    return {
        'statusCode': 200,
        'body': f'Video task deleted: {task_id}'
    }

def delete_s3_vectors(output_s3_bucket, output_s3_prefix, s3_vector_bucket, s3_vector_index, task_id):
    # Get vectors Keys from S3 Tlabs output json
    response = s3.list_objects_v2(Bucket=output_s3_bucket, Prefix=output_s3_prefix)
    # Look for output.json
    keys = []
    output_key = None
    for obj in response.get('Contents', []):
        if obj['Key'].endswith('output.json'):
            output_key = obj['Key']
            if output_key:
                #print("!!!", output_key)
                obj = s3.get_object(Bucket=output_s3_bucket, Key=output_key)
                content = obj['Body'].read().decode('utf-8')
                output = json.loads(content).get("data")
                if output:
                    for item in output:
                        key = f'{task_id}_{item["embeddingOption"]}_{item["startSec"]}_{item["endSec"]}'
                        if key not in keys:
                            keys.append(key)

    # Delete vectors from S3
    if keys:
        response = s3vectors.delete_vectors(
            vectorBucketName=s3_vector_bucket,
            indexName=s3_vector_index,
            keys=keys
        )

def delete_s3_folder(s3_bucket, s3_prefix):
    # List objects in the folder
    objects_to_delete = []
    paginator = s3.get_paginator('list_objects_v2')
    for result in paginator.paginate(Bucket=s3_bucket, Prefix=s3_prefix):
        if 'Contents' in result:
            for obj in result['Contents']:
                objects_to_delete.append({'Key': obj['Key']})
    
    # Delete objects in batches of 1000 (maximum allowed)
    delete_responses = []
    for i in range(0, len(objects_to_delete), 1000):
        delete_batch = {'Objects': objects_to_delete[i:i+1000]}
        delete_response = s3.delete_objects(Bucket=s3_bucket, Delete=delete_batch)
        delete_responses.append(delete_response)
    
    return delete_responses