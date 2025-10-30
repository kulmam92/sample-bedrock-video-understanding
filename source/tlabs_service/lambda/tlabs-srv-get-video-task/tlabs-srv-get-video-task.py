import json
import boto3
import os
import utils
from datetime import datetime

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
DYNAMO_VIDEO_FRAME_TABLE = os.environ.get("DYNAMO_VIDEO_FRAME_TABLE")
DYNAMO_VIDEO_TRANS_TABLE = os.environ.get("DYNAMO_VIDEO_TRANS_TABLE")

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
    
    # Supported values: 
    # ["Request","VideoMetaData",
    #   "Transcription","DetectLabel","DetectLabelCategory","DetectText","DetectCelebrity","DetectModeration","DetectLogo","ImageCaption",
    #   "DetectLabelAgg","DetectLabelCategoryAgg","DetectTextAgg","DetectCelebrityAgg","DetectModerationAgg","DetectLogoAgg"
    # ]
    data_types = event.get("DataTypes", ["Request","VideoMetaData","Subtitle","DetectLabelCategoryAgg","DetectTextAgg","DetectCelebrityAgg","DetectModerationAgg"]) 
    page_size = event.get("PageSize", 500)
    from_index = event.get("FromIndex", 0)

    # get from video_task DB table
    db_task = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    if db_task is None:
        return {
            'statusCode': 400,
            'body': f'Invalid request. Task does not exist: {task_id}.'
        }
    
    task = {}
    if "Request" in data_types and "VideoMetaData" in data_types:
        task["Status"] = db_task["Status"]
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
            task["MetaData"]["VideoFrameS3"]["TotalFramesPlaned"] = float(task["MetaData"]["VideoFrameS3"]["TotalFramesPlaned"])
            task["MetaData"]["VideoFrameS3"]["TotalFramesSampled"] = float(task["MetaData"]["VideoFrameS3"]["TotalFramesSampled"])
            task["RequestTs"] = db_task["RequestTs"]
            task["EmbedCompleteTs"] = db_task.get("EmbedCompleteTs")
    
        except Exception as ex:
            print(ex)
    
    return {
        'statusCode': 200,
        'body': task
    }