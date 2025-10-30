import json
import boto3
import uuid
import utils
import os
from datetime import datetime, timezone

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
LAMBDA_FUN_NAME_VIDEO_METADATA = os.environ.get("LAMBDA_FUN_NAME_VIDEO_METADATA")
TWELVELABS_MODEL_ID = 'twelvelabs.marengo-embed-2-7-v1:0'

bedrock = boto3.client('bedrock-runtime')
lambda_client = boto3.client('lambda')
sts = boto3.client("sts")

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

    # TwelveLabs for now
    s3_bucket = event.get("Video",{}).get("S3Object").get("Bucket")
    s3_key = event.get("Video",{}).get("S3Object").get("Key")
    s3_prefix_output = f'tasks/{task_id}/tlabs/'
    model_id = event.get("ModelId",TWELVELABS_MODEL_ID)

    # Get account Id
    account_id = sts.get_caller_identity()["Account"]

    request = event.get("TLabsRequest")
    if request.get("startSec"):
        request["startSec"] = float(request["startSec"])
    if request.get("lengthSec"):
        request["lengthSec"] = float(request["lengthSec"])
    if request.get("useFixedLengthSec"):
        request["useFixedLengthSec"] = float(request["useFixedLengthSec"])
    if request.get("minClipSec"):
        request["minClipSec"] = int(request["minClipSec"])

    if not request:
        request = {
            "inputType": "video",
        }
    request["mediaSource"] = {
            "s3Location": {
                "uri": f's3://{s3_bucket}/{s3_key}',
                "bucketOwner": account_id
            }
        }

    # Start 12labs async task
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


    doc["Status"] = "processing"

    # Update DB
    response = utils.dynamodb_table_upsert(DYNAMO_VIDEO_TASK_TABLE, doc)
        
    return {
        'statusCode': 200,
        'body': {
            "TaskId": task_id
        }
    }
