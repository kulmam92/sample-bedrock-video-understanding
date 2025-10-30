'''
"Source": mm_embedding | text_embedding | text,
'''
import json
import boto3
import os
import utils
import re
from urllib.parse import urlparse

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
DYNAMO_VIDEO_FRAME_TABLE = os.environ.get("DYNAMO_VIDEO_FRAME_TABLE")
DYNAMO_VIDEO_TRANS_TABLE = os.environ.get("DYNAMO_VIDEO_FRAME_TABLE")

S3_PRESIGNED_URL_EXPIRY_S = os.environ.get("S3_PRESIGNED_URL_EXPIRY_S", 3600) # Default 1 hour 

s3 = boto3.client('s3')

def lambda_handler(event, context):
    task_id = event.get("TaskId")
    page_size = event.get("PageSize", 20)
    from_index = event.get("FromIndex", 0)

    if task_id is None:
        return {
            'statusCode': 400,
            'body': 'TaskId required.'
        }

    result = {"Frames":[], "Total": utils.count_items_by_task_id(DYNAMO_VIDEO_FRAME_TABLE, task_id)}
    frames = utils.get_paginated_items(table_name=DYNAMO_VIDEO_FRAME_TABLE, task_id=task_id, start_index=from_index, page_size=page_size)
    for f in frames:
        try:
            frame = {
                "S3Url": s3.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': f["s3_bucket"], 'Key': f["s3_key"]},
                            ExpiresIn=S3_PRESIGNED_URL_EXPIRY_S
                        ),
                "Timestamp": f["timestamp"],
            }
            if f.get("frame_outputs"):
                frame["CustomOutputs"] = f["frame_outputs"]

            frame["PrevTs"] = f.get("prev_timestamp")
            frame["SimilarityScore"] = f.get("similarity_score")

            result["Frames"].append(frame)
        except Exception as ex:
            print(ex)
    return {
        'statusCode': 200,
        'body': result
    }
