'''
"Source": mm_embedding | text_embedding | text,
'''
import json
import boto3
import os
import utils
import re
from urllib.parse import urlparse

DYNAMO_VIDEO_TRANS_TABLE = os.environ.get("DYNAMO_VIDEO_TRANS_TABLE")

def lambda_handler(event, context):
    task_id = event.get("TaskId")
    page_size = event.get("PageSize", 20)
    from_index = event.get("FromIndex", 0)

    if task_id is None:
        return {
            'statusCode': 400,
            'body': 'TaskId required.'
        }

    result = {"Transcripts":[], "Total": utils.count_items_by_task_id(table_name=DYNAMO_VIDEO_TRANS_TABLE, task_id=task_id)}
    transcripts = utils.get_paginated_items(table_name=DYNAMO_VIDEO_TRANS_TABLE, task_id=task_id, start_index=from_index, page_size=page_size)
    for t in transcripts:
        try:
            result["Transcripts"].append({
                "StartTs": t["start_ts"],
                "EndTs": t["end_ts"],
                "Transcript": t["transcription"]
            })
        except Exception as ex:
            print(ex)
    

    return {
        'statusCode': 200,
        'body': result
    }
