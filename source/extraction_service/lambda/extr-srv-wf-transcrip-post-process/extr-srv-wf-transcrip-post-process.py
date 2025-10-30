import json
import boto3
import os
import utils
import re

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
DYNAMO_VIDEO_TRANS_TABLE = os.environ.get("DYNAMO_VIDEO_TRANS_TABLE")

TRANSCRIPTION_S3_PREFIX_TEMPLATE = "tasks/{task_id}/transcribe/"

s3 = boto3.client('s3')

def lambda_handler(event, context):
    #print(json.dumps(event))
    if not event or "Request" not in event:
         return {
            'statusCode': 400,
            'body': 'Invalid request'
        }
    s3_bucket, task_id = None, None
    try:
        s3_bucket = event["Request"]["Video"]["S3Object"]["Bucket"]
        task_id = event["Request"]["TaskId"]
    except ex as Exception:
        print(ex)
        return {
            'statusCode': 400,
            'body': f'Invalid request'
        }
    s3_prefix = TRANSCRIPTION_S3_PREFIX_TEMPLATE.format(task_id=task_id)
    

    # Get transcript and vtt keys
    trans_key, vtt_key = None, None
    response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=s3_prefix)
    if 'Contents' in response:
        for c in response["Contents"]:
            if c["Key"].endswith(".json"):
                trans_key = c["Key"]
            elif c["Key"].endswith(".vtt"):
                vtt_key = c["Key"]

    # Get transcription result from S3
    if trans_key:
        response = s3.get_object(Bucket=s3_bucket, Key=trans_key)
        file_content = response['Body'].read().decode('utf-8')
        trans_data = json.loads(file_content)
    
    # Get subtitle from S3
    if vtt_key:
        subtitle_data = read_vtt(s3_bucket, vtt_key)
    
    # Get task doc from db
    doc = None
    try:
        doc = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, id=task_id)
    except Exception as ex:
        print('Doc does not exist',ex)
    
    if doc is not None:
        # Update video task: metadata.transcription output
        try:
            metadata = doc.get("MetaData", {})
            if "Audio" not in metadata:
                metadata["Audio"] = {"Language": None}
            if not metadata["Audio"].get("Language"):
                metadata["Audio"]["Language"] = trans_data["results"]["language_code"]

                doc["MetaData"] = metadata
                event["MetaData"] = metadata
                doc["Id"] = task_id
            
                # update DB: video_task
                utils.dynamodb_table_upsert(DYNAMO_VIDEO_TASK_TABLE, utils.convert_to_dynamo_format(doc))
        except Exception as ex:
            print('Failed to update video task status',ex)

        # Update transciption to DB
        try:
            # add transcription to db: video_transcription
            for sub in subtitle_data:
                sub["id"] = f"{task_id}_{sub['start_ts']}_{sub['end_ts']}"
                sub["task_id"] = task_id
                utils.dynamodb_table_upsert(DYNAMO_VIDEO_TRANS_TABLE, utils.convert_to_dynamo_format(sub))
        except Exception as ex:
            print('Failed to update transcription to DB',ex)

    return event

def read_vtt(s3_bucket, s3_key):
    # Read transcription file
    s3_clientobj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
    s3_clientdata = s3_clientobj["Body"].read().decode("utf-8")

    subtitles = []
    blocks = re.split(r'\n{2,}', s3_clientdata.strip())
    for block in blocks:
        lines = block.split('\n')
        if len(lines) <= 1:
            continue
        # Extract index, timecodes, and text
        index = int(lines[0]) if lines and lines[0].isdigit() else None
        timecodes = re.findall(r'(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})', lines[1])
        text = '\n'.join(lines[2:]).strip() if len(lines) > 2 else None

        if index is not None and timecodes and text is not None:
            start_ts, end_ts = timecodes[0]
            subtitles.append({
                "start_ts": convert_timestamp_to_ms(start_ts),
                "end_ts": convert_timestamp_to_ms(end_ts),
                "transcription": text
            })
    return subtitles

def convert_timestamp_to_ms(timestamp):
    try:
        # Split the timestamp into hours, minutes, seconds, and milliseconds
        hours, minutes, seconds_ms = timestamp.split(':')
        seconds, milliseconds = seconds_ms.split('.')
        
        # Convert to float and format the result
        result = float(hours) * 3600 + float(minutes) * 60 + float(seconds) + float(f"0.{milliseconds}")
        
        return round(result, 2)  # Round to 2 decimal places
    except ValueError as e:
        print(f"Error converting timestamp: {e}")
        return None
