import json
import boto3
import os
import utils
import base64
import cv2
import numpy as np

DYNAMO_VIDEO_FRAME_TABLE = os.environ.get("DYNAMO_VIDEO_FRAME_TABLE")
DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
VIDEO_FRAME_SIMILAIRTY_THRESHOLD_DEFAULT = float(os.environ.get("VIDEO_FRAME_SIMILAIRTY_THRESHOLD_DEFAULT","0.1"))
VIDEO_SAMPLE_FILE_PREFIX = os.environ.get("VIDEO_SAMPLE_FILE_PREFIX")

s3 = boto3.client('s3')

def lambda_handler(event, context):
    task_id, start_ts, end_ts = None, None, None
    try:
        task_id = event["task_id"]
        start_ts = float(event["start_ts"])
        end_ts = float(event["end_ts"])
    except Exception as ex:
        print(ex)
        return 'Invalid request'

    task = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    if task is None:
        return 'Invalid request'

    enable_smart_sampling = False
    try:
        enable_smart_sampling = task["Request"]["PreProcessSetting"]["SmartSample"] == True
    except Exception as ex:
        print(ex)
    
    if not enable_smart_sampling:
        return event

    similarity_threshold = VIDEO_FRAME_SIMILAIRTY_THRESHOLD_DEFAULT
    if "SimilarityThreshold" in task["Request"]["PreProcessSetting"]:
        try:
            similarity_threshold = float(task["Request"]["PreProcessSetting"]["SimilarityThreshold"])
        except Exception as ex:
            print(ex)
            
    # Read image frames from S3
    s3_bucket = task["MetaData"]["VideoFrameS3"]["S3Bucket"]
    s3_prefix = task["MetaData"]["VideoFrameS3"]["S3Prefix"]
    total_frames = task["MetaData"]["VideoFrameS3"]["TotalFramesPlaned"]

    video_duration = float(task["MetaData"]["VideoMetaData"]["Duration"])
    timestamps = generate_sample_timestamps(task["Request"].get("PreProcessSetting"), video_duration, start_ts, end_ts)
    
    prev_ts, prev_data, total_sampled = start_ts, None, 0
    for ts in timestamps:
        cur_ts = ts["ts"]
        try:
            # Get current image bytes
            cur_s3_key = f"{s3_prefix}/{VIDEO_SAMPLE_FILE_PREFIX}{cur_ts}.png"
            cur_data = read_image_from_s3(s3_bucket, cur_s3_key)

            if cur_data is not None:
                # Get previous image bytes
                prev_data = read_image_from_s3(s3_bucket, f"{s3_prefix}/{VIDEO_SAMPLE_FILE_PREFIX}{prev_ts}.png")

                if prev_data is not None:
                    # Compare: ORB (Oriented FAST and Rotated BRIEF)
                    score, matches, kp1, kp2 = orb_similarity(prev_data, cur_data)
                else:
                    score = None

                if score is not None and score >= similarity_threshold:
                    # Delete image on S3
                    s3.delete_object(Bucket=s3_bucket, Key=cur_s3_key)

                    # Delete from DB video_frame table
                    frame_id = f'{task_id}_{cur_ts}'
                    response = utils.dynamodb_delete_by_id(DYNAMO_VIDEO_FRAME_TABLE, frame_id, task_id)

                else:
                    # set current image as prev
                    prev_data = cur_data
                    prev_ts = cur_ts

                    total_sampled += 1
                    
                    # update frame in db: include similarity score
                    if score:
                        response = utils.update_item_with_similarity_score(DYNAMO_VIDEO_FRAME_TABLE, f'{task_id}_{cur_ts}', task_id, score)
                #break

        except Exception as e:
            print(e)

    # update video_task table
    try:
        # Get task from DB
        task_db = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
        sampled = float(task_db["MetaData"]["VideoFrameS3"]["TotalFramesSampled"])
        task_db["MetaData"]["VideoFrameS3"]["TotalFramesSampled"] = sampled + float(total_sampled)
        # Update DB
        utils.dynamodb_table_upsert(DYNAMO_VIDEO_TASK_TABLE, task_db)
    except Exception as ex:
        print(ex)

def read_image_from_s3(bucket, key):
    img = None
    try:
        # Get image bytes
        obj = s3.get_object(Bucket=bucket, Key=key)
        img_bytes = obj['Body'].read()
        
        # Convert to NumPy array
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)  # grayscale for feature detection
    except Exception as ex:
        print(ex)
    return img

def orb_similarity(img1, img2):
    # ORB detector
    orb = cv2.ORB_create()
    kp1, des1 = orb.detectAndCompute(img1, None)
    kp2, des2 = orb.detectAndCompute(img2, None)

    # Handle case when no features found
    if des1 is None or des2 is None:
        return 0.0

    # Match descriptors
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)

    # Compute normalized similarity score
    similarity = len(matches) / max(len(kp1), len(kp2))
    return similarity, matches, kp1, kp2

def generate_sample_timestamps(setting, duration, sample_start_s, sample_end_s):
    if setting is None or "SampleMode" not in setting or "SampleIntervalS" not in setting:
        return None
    
    timestamps = []
    if setting["SampleMode"] == "even":
        current_time = 0.0
    
        # Generate timestamps at regular intervals
        while current_time <= duration:
            if current_time > sample_start_s and current_time <= sample_end_s:
                timestamps.append({"ts": current_time})
            current_time += float(setting["SampleIntervalS"])

    return timestamps