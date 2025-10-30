import json
import boto3
import re
import numbers,decimal
from boto3.dynamodb.conditions import Key
import os
import time

DYNAMO_VIDEO_ANALYSIS_TABLE = os.environ.get("DYNAMO_VIDEO_ANALYSIS_TABLE")
DYNAMO_VIDEO_FRAME_TABLE = os.environ.get("DYNAMO_VIDEO_FRAME_TABLE")
EXTR_SRV_S3_BUCKET = os.environ.get("EXTR_SRV_S3_BUCKET")

SHOT_SIMILARITY_THRESHOLD_DEFAULT = 0.9
S3_KEY_PREFIX = "tasks/{task_id}/shot/"
S3_FILE_TEMPLATE = "shot_{index}.json"
S3_KEY_TEMPLATE = S3_KEY_PREFIX + S3_FILE_TEMPLATE

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

video_analysis_table = dynamodb.Table(DYNAMO_VIDEO_ANALYSIS_TABLE)
video_frame_table = dynamodb.Table(DYNAMO_VIDEO_FRAME_TABLE)

def lambda_handler(event, context):
    task_id = event.get("Request",{}).get("TaskId")
    if not task_id:
        return {
            'statusCode': 200,
            'body': 'Task Id is required.'
        }

    shot_config = event.get("Request",{}).get("AnalysisSetting", {}).get("Shot")
    if not shot_config or shot_config.get("Enabled", False) == False:
        # Shot analysis is not required
        return event

    similarity_method = event.get("Request",{}).get("PreProcessSetting",{}).get("SimilarityMethod")
    if not similarity_method:
        similarity_method = "novamme"
    shot_similarity_threshold = float(shot_config.get("SimilarityThreshold", SHOT_SIMILARITY_THRESHOLD_DEFAULT))
        
    # Get all frames from DB (contains smiliarity score)
    frames = []
    last_evaluated_key = None
    while True:
        if last_evaluated_key:
            response = video_frame_table.query(
                IndexName='task_id-timestamp-index', 
                KeyConditionExpression=Key('task_id').eq(task_id), 
                ExclusiveStartKey=last_evaluated_key,
                Limit=1000
            )
        else:
            response = video_frame_table.query(
                IndexName='task_id-timestamp-index',
                KeyConditionExpression=Key('task_id').eq(task_id),
                Limit=1000
            )
        frames.extend(response.get("Items", []))
        last_evaluated_key = response.get('LastEvaluatedKey', None)
        if not last_evaluated_key:
            break
    frames = convert_dynamo_to_json_format(frames)

    # Iterating through Frames and group shots based on similiarity score
    shots = []
    start_ts, end_ts, shot_frames = None, None, []
    for frame in frames:
        ts = frame.get("timestamp")
        if start_ts is None:
            start_ts = ts
        score = frame.get("similarity_score")
        if score and ((similarity_method == "novamme" and score > shot_similarity_threshold) or (similarity_method == "orb" and score < shot_similarity_threshold)):
            shots.append({
                "start_ts": start_ts,
                "end_ts": ts,
                "duration": ts - start_ts,
                "frames": shot_frames
            })
            start_ts = ts
            shot_frames = []
        shot_frames.append({
            "timestamp": frame["timestamp"],
            "s3_bucket": frame["s3_bucket"],
            "s3_key": frame["s3_key"],
            "frame_summary": frame.get("frame_summary"),
            "similarity_score": score,
        })
    # include the last shot
    if shot_frames:
        shots.append({
                    "start_ts": start_ts,
                    "end_ts": ts,
                    "duration": ts - start_ts,
                    "frames": shot_frames
                })

    # Cleanup existing shots in DB and S3
    cleanup(task_id, EXTR_SRV_S3_BUCKET, S3_KEY_PREFIX)

    # Store shots to DB
    index = 0
    for s in shots:
        index += 1

        # Store to DB
        s["id"] = f"{task_id}_shot_{index}"
        s["index"] = index
        s["task_id"] = task_id
        s["analysis_type"] = 'shot'
        resposne = video_analysis_table.put_item(Item=convert_to_dynamo_format(s))

        # Store to S3
        s3.put_object(Bucket=EXTR_SRV_S3_BUCKET, 
            Key=S3_KEY_TEMPLATE.format(task_id=task_id, index=index), 
            Body=json.dumps(s), 
            ContentType='application/json'
        )
    event["shot_s3_bucket"] = EXTR_SRV_S3_BUCKET
    event["shot_s3_prefix"] = S3_KEY_PREFIX.format(task_id=task_id)[:-1]
    #event["shots"] = shots
    return event

def convert_to_dynamo_format(item):
    """
    Recursively convert an object to a DynamoDB item format.
    """
    if isinstance(item, dict):
        return {k: convert_to_dynamo_format(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [convert_to_dynamo_format(v) for v in item]
    elif isinstance(item, float):
        return decimal.Decimal(str(item))
    #elif isinstance(item, decimal.Decimal):
    #    return float(item)
    else:
        return item

def convert_dynamo_to_json_format(item):
    """
    Recursively convert a DynamoDB item to a JSON serializable format.
    """
    if isinstance(item, dict):
        return {k: convert_dynamo_to_json_format(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [convert_dynamo_to_json_format(v) for v in item]
    elif isinstance(item, decimal.Decimal):
        return float(item)
    else:
        return item

def cleanup(task_id, s3_bucket, s3_prefix):
    # Delete existing shot from DB
    response = video_analysis_table.query(
        IndexName='task_id-analysis_type-index',
        KeyConditionExpression=Key('task_id').eq(task_id) & 
                               Key('analysis_type').eq('shot')
    )
    for item in response['Items']:
        video_analysis_table.delete_item(
            Key={
                'id': item['id'], 
                'task_id': item['task_id']
            }
        )    
    
    # Delete s3 shot folder
    s3_res = boto3.resource('s3')
    bucket = s3_res.Bucket(s3_bucket)
    bucket.objects.filter(Prefix=s3_prefix).delete()
