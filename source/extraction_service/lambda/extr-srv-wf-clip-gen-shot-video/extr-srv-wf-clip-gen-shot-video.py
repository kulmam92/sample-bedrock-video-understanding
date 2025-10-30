import json
import boto3
import utils
import os
from moviepy import VideoFileClip

DYNAMO_VIDEO_SHOT_TABLE = os.environ.get("DYNAMO_VIDEO_SHOT_TABLE")

s3 = boto3.client('s3')

S3_KEY_TEMPLATE = "tasks/{task_id}/shot_clip/shot_{index}_{start_time}_{end_time}.mp4"
local_path = '/tmp/'

def lambda_handler(event, context):
    if event is None:
        return 'Invalid request'

    task_id = event.get("task_id")
    s3_source_bucket = s3_dest_bucket = event.get("s3_bucket")
    s3_source_key = event.get("s3_key")
    shots = event.get("shots")
    if not task_id or not s3_source_bucket or not s3_source_key or not shots:
        return 'Invalid Request'
        
    # Generate shot clip videos
    # Ensure the temporary directory exists
    temp_dir = "/tmp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # 1. Download the video from S3
    local_source_path = os.path.join(temp_dir, os.path.basename(s3_source_key))
    print(f"Downloading {s3_source_key} from {s3_source_bucket}...")
    s3.download_file(s3_source_bucket, s3_source_key, local_source_path)

    # 2. Open the video with MoviePy
    try:
        with VideoFileClip(local_source_path) as video:
            # 3. Generate and upload each clip
            for shot in shots:
                i = shot["index"]
                start_time = shot["start_time"]
                end_time = shot["end_time"]

                local_dest_path = os.path.join(temp_dir, f"clip_{i}.mp4")
                s3_dest_key = S3_KEY_TEMPLATE.format(task_id=task_id, index=i, start_time=start_time, end_time=end_time)

                print(f"Generating clip {i} (Start: {start_time}s, End: {end_time}s)...")
                
                # Use MoviePy's subclipped to cut the video
                # The subclipped method is used in version 2.x
                clip = video.subclipped(start_time, end_time)
                clip.write_videofile(local_dest_path, 
                    codec="libx264", 
                    audio_codec="aac",
                    temp_audiofile="/tmp/temp-audio.m4a",
                    remove_temp=True
                )
                
                print(f"Uploading {local_dest_path} to {s3_dest_bucket}/{s3_dest_key}...")
                s3.upload_file(local_dest_path, s3_dest_bucket, s3_dest_key)
                print(f"Upload complete for clip {i}.")
                
                shot["s3_bucket"] = s3_dest_bucket
                shot["s3_key"] = s3_dest_key
                shot["task_id"] = task_id

                # Clean up the local clip file
                os.remove(local_dest_path)

                # Update db to include clip s3 location
                update_shot_to_db(task_id, i, s3_dest_bucket, s3_dest_key)

    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        # 4. Clean up the local source file
        if os.path.exists(local_source_path):
            os.remove(local_source_path)
            print("Processing complete and temporary files cleaned up.")

    event["shots"] = shots
    return event

def update_shot_to_db(task_id, index, s3_bucket, s3_key):
    shot_id = f'{task_id}_shot_{index}'
    shot = utils.dynamodb_get_by_id(DYNAMO_VIDEO_SHOT_TABLE, shot_id, key_name="id", sort_key_value=task_id, sort_key="task_id")
    if shot:
        shot["s3_bucket"] = s3_bucket
        shot["s3_key"] = s3_key
        utils.dynamodb_table_upsert(DYNAMO_VIDEO_SHOT_TABLE, shot)    
    return shot

