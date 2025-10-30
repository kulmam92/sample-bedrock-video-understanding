'''
Delete video task
1. Delete S3 folder: frames, extraction raw files
2. Delete Transcribe job
3. Delete from OpenSearch: video_task, video_transcription, video_frame_[task_id]
'''
import json
import boto3
import os
import utils

TRANSCRIBE_JOB_PREFIX = os.environ.get("TRANSCRIBE_JOB_PREFIX")

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
DYNAMO_VIDEO_FRAME_TABLE = os.environ.get("DYNAMO_VIDEO_FRAME_TABLE")
DYNAMO_VIDEO_TRANS_TABLE = os.environ.get("DYNAMO_VIDEO_TRANS_TABLE")
S3_BUCKET_DATA = os.environ.get("S3_BUCKET_DATA")

S3_VECTOR_BUCKET = os.environ.get("S3_VECTOR_BUCKET")
S3_VECTOR_INDEX = os.environ.get("S3_VECTOR_INDEX")
S3_KEY_PREFIX_VECTOR = "tasks/{task_id}/shot_vector/"
S3_KEY_PREFIX_TEMPLATE = "tasks/{task_id}/"

s3 = boto3.client('s3')
transcribe = boto3.client('transcribe')
s3vectors = boto3.client('s3vectors') 

def lambda_handler(event, context):
    task_id = event.get("task_id")
    if not task_id:
        return {
            'statusCode': 400,
            'body': 'Invalid message'
        }

    task = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    if task is None:
        print(f'Task does not exist in {DYNAMO_VIDEO_TASK_TABLE}: {task_id}')

    s3_prefix = S3_KEY_PREFIX_TEMPLATE.format(task_id=task_id)

    # Delete S3 vectors
    delete_s3_vectors(S3_BUCKET_DATA, S3_VECTOR_BUCKET, S3_VECTOR_INDEX, task_id)

    # Delete S3 folder
    try:
        delete_s3_folder(S3_BUCKET_DATA, f"tasks/{task_id}")
    except:
        print("Failed to delete the S3 folder")
    
    # Delete Transcribe Job
    try:
        job_name = TRANSCRIBE_JOB_PREFIX + task_id[0:10]
        transcribe.delete_transcription_job(TranscriptionJobName=job_name)
    except Exception as ex:
        print('Failed to delete the Transcribe transcription job.', ex)
    
    # Delete DB entries
    # Delete frames video_frame table
    try:
        utils.dynamodb_delete_frames_by_taskid(DYNAMO_VIDEO_FRAME_TABLE, task_id)
    except Exception as ex:
        print(f"Failed to delete video frame entries: {DYNAMO_VIDEO_FRAME_TABLE}", ex)

    # Delete video_transcription entry
    try:
        utils.delete_items_by_task_id(DYNAMO_VIDEO_TRANS_TABLE, task_id)
    except Exception as ex:
        print(f'Failed to delete task {task_id} from index: {DYNAMO_VIDEO_TRANS_TABLE}', ex)

    # Delete video_task entry
    try:
        utils.dynamodb_delete_task_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    except Exception as ex:
        print(f'Failed to delete task {task_id} from index: {DYNAMO_VIDEO_TASK_TABLE}', ex)
        
    
    return {
        'statusCode': 200,
        'body': f'Video task deleted. {task_id}'
    }


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

def delete_s3_vectors(s3_bucket, s3_vector_bucket, s3_vector_index, task_id):
    s3_prefix = S3_KEY_PREFIX_VECTOR.format(task_id=task_id)

    # Get vectors Keys from S3 vector key names
    keys = []
    # S3 Vector key format: f'{task_id}_{embed_type}_{index}'
    # S3 JSON file name format: f'{embed_type}_{index}.json'
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=s3_bucket, Prefix=s3_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".json"):
                keys.append(f'{task_id}_{key.replace(".json","")}')

    # Delete vectors from S3
    if keys:
        response = s3vectors.delete_vectors(
            vectorBucketName=s3_vector_bucket,
            indexName=s3_vector_index,
            keys=keys
        )