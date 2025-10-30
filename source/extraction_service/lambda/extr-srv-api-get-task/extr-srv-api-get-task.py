import json
import boto3
import os
import utils
from datetime import datetime

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
DYNAMO_VIDEO_FRAME_TABLE = os.environ.get("DYNAMO_VIDEO_FRAME_TABLE")
DYNAMO_VIDEO_TRANS_TABLE = os.environ.get("DYNAMO_VIDEO_TRANS_TABLE")
DYNAMO_VIDEO_SHOT_TABLE = os.environ.get("DYNAMO_VIDEO_SHOT_TABLE")

S3_PRESIGNED_URL_EXPIRY_S = os.environ.get("S3_PRESIGNED_URL_EXPIRY_S", 3600) # Default 1 hour 
s3 = boto3.client("s3")
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    task_id = event.get("TaskId")    
    if task_id is None:
        return {
            'statusCode': 400,
            'body': 'Invalid request. Missing TaskId.'
        }
    
    page_size = event.get("PageSize", 500)
    from_index = event.get("FromIndex", 0)

    # get from video_task DB table
    db_task = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    if db_task is None:
        return {
            'statusCode': 400,
            'body': f'Invalid request. Task does not exist: {task_id}.'
        }
    
    task = {"Status": db_task["Status"]}
    # Get Video pre-signed S3 URL
    s3_bucket = db_task["Request"]["Video"]["S3Object"]["Bucket"]
    s3_key = db_task["Request"]["Video"]["S3Object"]["Key"]
    task["Request"] = db_task["Request"]
    task["VideoUrl"] = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': s3_bucket, 'Key': s3_key},
            ExpiresIn=S3_PRESIGNED_URL_EXPIRY_S
        )
    task["MetaData"] = db_task["MetaData"]
    try:
        task["MetaData"]["VideoMetaData"]["Fps"] = float(task["MetaData"]["VideoMetaData"]["Fps"])
        task["MetaData"]["VideoMetaData"]["Size"] = float(task["MetaData"]["VideoMetaData"]["Size"])
        task["MetaData"]["VideoMetaData"]["Duration"] = float(task["MetaData"]["VideoMetaData"]["Duration"])
        if "VideoFrameS3" in task["MetaData"]:
            task["MetaData"]["VideoFrameS3"]["TotalFramesPlaned"] = float(task["MetaData"]["VideoFrameS3"]["TotalFramesPlaned"])
            task["MetaData"]["VideoFrameS3"]["TotalFramesSampled"] = float(task["MetaData"]["VideoFrameS3"]["TotalFramesSampled"])
        task["RequestTs"] = db_task["RequestTs"]
        task["ExtractionCompleteTs"] = db_task.get("ExtractionCompleteTs")

    except Exception as ex:
        print(ex)
    
    if "Request" in task and "TaskType" not in task["Request"]:
        task["Request"]["TaskType"] = "frame"
    
    # Get Transcription and Subtitles
    task["Transcription"] = utils.dynamodb_get_by_id(table_name=DYNAMO_VIDEO_TRANS_TABLE, id=task_id, key_name="task_id")
    
    # Get items
    frames = None
    return {
        'statusCode': 200,
        'body': task
    }

    
FRAMES = None
def get_items(task_id, field_name, from_index, page_size):
    global FRAMES
    if FRAMES is None:
        FRAMES = utils.get_paginated_items(table_name=DYNAMO_VIDEO_FRAME_TABLE, task_id=task_id, start_index=from_index, page_size=page_size)
        
    total = utils.count_items_by_task_id(DYNAMO_VIDEO_FRAME_TABLE, task_id)
    result = []
    for f in FRAMES:
        ts = float(f["timestamp"])
        print(ts)
        if field_name == "detect_label_category":
            items = f.get("detect_label")
            if items:
                for item in items:
                    if "categories" in item:
                        for c in item["categories"]:
                            result.append({
                                "value": c,
                                "timestamp": ts
                            })
        elif field_name == "image_caption":
            item = f.get(field_name)
            if item:
                result.append({
                        "value": item,
                        "timestamp": ts
                    })
        else:
            items = f.get(field_name)
            if items:
                for item in items:
                    result.append({
                            "value": item["name"],
                            "timestamp": ts
                        })
    
    # Sort result
    result.sort(key=lambda x: x['timestamp'], reverse=False)

    video_analysis_table = dynamodb.Table(DYNAMO_VIDEO_SHOT_TABLE)  
    items = []
    try:
        last_evaluated_key = None
        # Keep querying until there are no more pages of results
        while True:
            query_params = {
                'IndexName': 'task_id-analysis_type-index',  # Name of your index
                'KeyConditionExpression': 'task_id = :task_id_val AND analysis_type = :type_val',
                'ExpressionAttributeValues': {
                    ':task_id_val': task_id,
                    ':type_val': 'shot'
                }
            }
            if last_evaluated_key:
                query_params['ExclusiveStartKey'] = last_evaluated_key

            response = video_analysis_table.query(**query_params)
            for s in response.get('Items', []):
                i = {
                    "summary": s.get("summary"),
                    "start_ts": s.get("start_ts"),
                    "end_ts": s.get("end_ts"),
                    "transcripts": []
                }
                for f in s.get("frames",[]):
                    if f and f.get("subtitles"):
                        for sub in f.get("subtitles",[]):
                            if sub not in i["transcripts"]:
                                if sub.get("transcription"):
                                    if len(i["transcripts"]) > 0 and i["transcripts"][-1] == sub["transcription"]:
                                        continue
                                    i["transcripts"].append(sub["transcription"])
                items.append(i)
            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
    except Exception as ex:
        print(ex)
        return {
            'statusCode': 400,
            'body': f'Task {task_id} does not exist.'
        }

    items = sorted(items, key=lambda x: x['start_ts'], reverse=False)
    end_index = from_index + page_size
    if end_index > len(items):
        end_index = len(items)
    return items[from_index: end_index]