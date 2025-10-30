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

LAMBDA_NAME_DELETE_PROCESS = os.environ.get("LAMBDA_NAME_DELETE_PROCESS")
lambda_client = boto3.client("lambda")

def lambda_handler(event, context):
    task_id = event.get("TaskId")
    delete_s3 = event.get("DeleteS3", True)
    if task_id is None:
        return {
            'statusCode': 400,
            'body': json.dumps('Require TaskId')
        }
    
    # Invoke lambda - async deleting
    response = lambda_client.invoke(
        FunctionName=LAMBDA_NAME_DELETE_PROCESS,
        InvocationType="Event",  # async invocation
        Payload=json.dumps({"task_id": task_id})
    )

    return {
        'statusCode': 200,
        'body': f'Deleting video task: {task_id}'
    }

