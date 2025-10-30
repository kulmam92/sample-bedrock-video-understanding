import json
import boto3
import uuid
import utils
import os
from datetime import datetime, timezone

STEP_FUNCTIONS_STATE_MACHINE_ARN_FRAME = os.environ.get("STEP_FUNCTIONS_STATE_MACHINE_ARN_FRAME")
STEP_FUNCTIONS_STATE_MACHINE_ARN_CLIP = os.environ.get("STEP_FUNCTIONS_STATE_MACHINE_ARN_CLIP")
DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")

stepfunctions = boto3.client('stepfunctions')
bedrock = boto3.client('bedrock-runtime')

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
    if extra_option not in ["frame","clip"]:
        return {
            'statusCode': 400,
            'body': 'Invalid request'
        }

    # Determine which step function to use
    step_fun_arn = None
    if extra_option == "frame":
        step_fun_arn = STEP_FUNCTIONS_STATE_MACHINE_ARN_FRAME
    elif extra_option == "clip":
        step_fun_arn = STEP_FUNCTIONS_STATE_MACHINE_ARN_CLIP

    # Check if there are already running executions (threshold = 1)
    if step_fun_arn:
        try:
            running_executions = stepfunctions.list_executions(
                stateMachineArn=step_fun_arn,
                statusFilter='RUNNING'
            )
            
            if len(running_executions['executions']) >= 1:
                return {
                    'statusCode': 409,
                    'body': {
                        'error': 'There is a task in progress. Please wait until it completes before starting a new task.'
                    }
                }
        except Exception as e:
            print(f"Error checking running executions: {str(e)}")
            # Continue with execution if we can't check status

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

    if step_fun_arn:
        # Start stepfunction workflow
        stepfunctions.start_execution(
            stateMachineArn=step_fun_arn,
            input=json.dumps({"Request":event})
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