import json
import boto3
import uuid
import utils
import os
from datetime import datetime, timezone

TRANSCRIBE_JOB_PREFIX = os.environ.get("TRANSCRIBE_JOB_PREFIX")
TRANSCRIBE_OUTPUT_BUCKET = os.environ.get('TRANSCRIBE_OUTPUT_BUCKET')
TRANSCRIBE_OUTPUT_PREFIX = os.environ.get('TRANSCRIBE_OUTPUT_PREFIX')

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
transcribe = boto3.client('transcribe', region_name=AWS_REGION)

def lambda_handler(event, context):
    if not event\
            or "Request" not in event:
        return {
            'statusCode': 200,
            'body': 'Invalid request'
        }
    
    # Get task Id. Create a new one if not provided.
    task_id = event["Request"].get("TaskId")
    
    transcribe_output_key = f'tasks/{task_id}/{TRANSCRIBE_OUTPUT_PREFIX}/{task_id}_transcribe.json'

    # Upsert DB
    doc = {
        "Id": task_id,
        "Request": event["Request"],
        "RequestTs": datetime.now(timezone.utc).isoformat(),
        "RequestBy": event["Request"].get("RequestBy"),
        "MetaData": {
            "TrasnscriptionOutput": f's3://{TRANSCRIBE_OUTPUT_BUCKET}/{transcribe_output_key}'
        },
        "Status": "processing"
    }
    utils.dynamodb_table_upsert(DYNAMO_VIDEO_TASK_TABLE, doc)

    job_name = TRANSCRIBE_JOB_PREFIX + task_id[0:10]

    # Check if job exists. If so delete it.
    try:
        status_response = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        if status_response:
            job_status = status_response.get('TranscriptionJob',{}).get('TranscriptionJobStatus')
            if job_status and job_status in ['IN_PROGRESS', 'FAILED', 'COMPLETED']:
                print(f"Deleting existing job: {job_name} (Status: {job_status})")
                transcribe.delete_transcription_job(TranscriptionJobName=job_name)
    except Exception as ex:
        print(ex)

    # Start transcription job
    try:
        response = transcribe.start_transcription_job(
                TranscriptionJobName = job_name,
                Media = { 'MediaFileUri': f's3://{event["Request"]["Video"]["S3Object"]["Bucket"]}/{event["Request"]["Video"]["S3Object"]["Key"]}'},
                OutputBucketName = TRANSCRIBE_OUTPUT_BUCKET, 
                OutputKey = transcribe_output_key,
                IdentifyLanguage=True,
                Subtitles = {
                    'Formats': ['vtt'],
                    'OutputStartIndex': 1 
                }
            ) 
        event["TranscriptionJob"] = {"TranscriptionJobName": response["TranscriptionJob"]["TranscriptionJobName"]}
    except Exception as ex:
        print(ex)
    
    # Include job name and output location to the response
    return event

