import json
import boto3
import utils
import os
from datetime import datetime, timezone

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")

def lambda_handler(event, context):
    if not event:
        return {
            "Error": "Invalid Request"
        }
    
    for input in event:
        if "Request" in input:
            task_id = input["Request"].get("TaskId")
            break
    if not task_id:
        return {
            "Error": "Invalid Request"
        }

    task = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    task["Status"] = "extraction_completed"
    task["ExtractionCompleteTs"] = datetime.now(timezone.utc).isoformat()
    utils.dynamodb_table_upsert(DYNAMO_VIDEO_TASK_TABLE, task)

    return event