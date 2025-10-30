import json
import boto3
import uuid
import utils
import os
import botocore
from datetime import datetime, timezone

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
LAMBDA_FUN_NAME_VIDEO_METADATA = os.environ.get("LAMBDA_FUN_NAME_VIDEO_METADATA")
EMBEDDING_DIM = os.environ.get("EMBEDDING_DIM")
DEFAULT_NOVA_MME_MODEL_ID = os.environ.get("DEFAULT_NOVA_MME_MODEL_ID")

EMBEDDING_DIM = int(EMBEDDING_DIM) if EMBEDDING_DIM else 1024

bedrock = boto3.client('bedrock-runtime')
lambda_client = boto3.client('lambda')
s3 = boto3.client("s3")

def lambda_handler(event, context):
    if event is None \
            or "Video" not in event \
            or "S3Object" not in event["Video"]:
        return {
            'statusCode': 400,
            'body': 'Invalid request'
        }
    
    # Get task Id. Create a new one if not provided.
    task_id = event.get("TaskId")
    if not task_id:
        return {
            'statusCode': 400,
            'body': 'Invalid request'
        }
    
    extra_option = event.get("TaskType", "frame")

    # Store to DB
    doc = {
        "Id": task_id,
        "Request": event,
        "RequestTs": datetime.now(timezone.utc).isoformat(),
        "RequestBy": event.get("RequestBy"),
        "Name": event.get("Name", event.get("FileName")),
        "MetaData": {
            "TrasnscriptionOutput": None
        }
    }

    s3_bucket = event.get("Video",{}).get("S3Object").get("Bucket")
    s3_key = event.get("Video",{}).get("S3Object").get("Key")
    s3_prefix_output = f'tasks/{task_id}/nova-mme/'
    model_id = event.get("ModelId",DEFAULT_NOVA_MME_MODEL_ID)
    embed_mode = event.get("EmbedMode", "AUDIO_VIDEO_COMBINED")
    duration_s = int(event.get("DurationS", 5))
    video_format = s3_key.split("/")[-1].split(".")[-1].lower()

    # temp workaround before Nova fix output support prefix
    # Create output folder if not exists
    tmp_key = s3_prefix_output + ".tmp"
    try:
        # Check if placeholder exists
        s3.head_object(Bucket=s3_bucket, Key=tmp_key)
        print(f"Folder already exists: s3://{s3_bucket}/{tmp_key}")
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            # Create placeholder file
            s3.put_object(Bucket=s3_bucket, Key=tmp_key, Body=b"")
            print(f"Created folder: s3://{s3_bucket}/{tmp_key}")

    request = {
            "taskType": "SEGMENTED_EMBEDDING",
            "segmentedEmbeddingParams": {
                "embeddingDimension": EMBEDDING_DIM,
                "embeddingPurpose": "GENERIC_INDEX",
                "video": {
                    "format": video_format,
                    "embeddingMode": embed_mode,
                    "source": {
                        "s3Location": {
                            "uri": f's3://{s3_bucket}/{s3_key}',
                        }
                    },
                    "segmentationConfig": {"durationSeconds": duration_s},
                },
            },
        }

    try:
        # Start Nova MME async task
        response = bedrock.start_async_invoke(
            modelId=model_id,
            modelInput=request,
            outputDataConfig={
                "s3OutputDataConfig": {
                    "s3Uri": f's3://{s3_bucket}/{s3_prefix_output}'
                }
            }
        )
        print("Task arn:", response["invocationArn"])

        # Start video metadata task
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUN_NAME_VIDEO_METADATA,
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps({"Request": event})
        )
    except Exception as ex:
        return {
            'statusCode': 500,
            'error': str(ex)
        }


    doc["Status"] = "processing"

    # Update DB
    response = utils.dynamodb_table_upsert(DYNAMO_VIDEO_TASK_TABLE, doc)
        
    return {
        'statusCode': 200,
        'body': {
            "TaskId": task_id
        }
    }
