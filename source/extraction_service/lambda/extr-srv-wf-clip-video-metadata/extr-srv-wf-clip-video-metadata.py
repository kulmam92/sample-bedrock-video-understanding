import json
import boto3
import os
import base64
from moviepy import VideoFileClip
import utils
import time

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
DYNAMO_VIDEO_USAGE_TABLE = os.environ.get("DYNAMO_VIDEO_USAGE_TABLE")

VIDEO_SAMPLE_S3_BUCKET = os.environ.get("VIDEO_SAMPLE_S3_BUCKET")
VIDEO_SAMPLE_S3_PREFIX = os.environ.get("VIDEO_SAMPLE_S3_PREFIX")
MODEL_ID_IMAGE_UNDERSTANDING = os.environ.get("MODEL_ID_IMAGE_UNDERSTANDING")

IMAGE_MAX_WIDTH = 2048
IMAGE_MAX_HEIGHT = 2048

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')

local_path = '/tmp/'

def lambda_handler(event, context):
    if event is None or "Request" not in event:
        return 'Invalid request'
    
    task_id = event["Request"].get("TaskId")
    s3_bucket, s3_key = None, None
    try:
        s3_bucket = event["Request"]["Video"]["S3Object"]["Bucket"]
        s3_key = event["Request"]["Video"]["S3Object"]["Key"]
    except:
        return 'Invalid Request'

    # Download video to local disk
    local_file_path = local_path + s3_key.split('/')[-1]
    s3.download_file(s3_bucket, s3_key, local_file_path)
    print(f"{s3_bucket}{s3_key}")
    
    # Generate thumbnail and video metadata
    if "MetaData" not in event:
        event["MetaData"] = {}
    video_metadata = get_video_metadata(event, local_file_path)
    duration = video_metadata["Duration"]

    task = event
    task_db = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    if task_db:
        task["Id"] = task_db["Id"]
        task["RequestBy"] = task_db.get("RequestBy")
        task["RequestTs"] = task_db.get("RequestTs")
        task["Status"] = task_db.get("Status")

    task["MetaData"]["VideoMetaData"] = video_metadata
    
    task["Status"] = "processing"

    try:
        # update video_task index
        utils.dynamodb_table_upsert(DYNAMO_VIDEO_TASK_TABLE, document=task)
    except Exception as ex:
        print(ex)
       
    return task
        
def get_video_metadata(event, file_path):
    video_file_name = event["Request"]["Video"]["S3Object"]["Key"].split('/')[-1]
    thumbnail_local_path = f'{local_path}thumbnail.jpeg'
    thumbnail_s3_bucket = event["Request"]["Video"]["S3Object"]["Bucket"]
    thumbnail_s3_key = f'{event["Request"]["Video"]["S3Object"]["Key"].replace(video_file_name, "thumbnail.jpeg")}'
    task_id = event["Request"].get("TaskId")

    video_clip = VideoFileClip(file_path)    
    # Get thumbnail - avoid black screen
    for i in range(0, int(video_clip.duration)):
        # Get frame and store on local disk
        video_clip.save_frame(thumbnail_local_path, t=i)
        # Upload to S3
        s3.upload_file(thumbnail_local_path, thumbnail_s3_bucket, thumbnail_s3_key)
        
        # Check if image is black frame
        is_black_frame = is_single_color_frame(task_id, i, thumbnail_s3_bucket, thumbnail_s3_key)
        if is_black_frame is not None and is_black_frame == True:
            break
    
    # construct metadata
    metadata = {
        'Size': os.path.getsize(file_path),
        'Resolution': video_clip.size,
        'Duration': video_clip.duration,
        'Fps': video_clip.fps,
        'NameFormat': file_path.split('.')[-1],
        'ThumbnailS3Bucket': thumbnail_s3_bucket,
        'ThumbnailS3Key': thumbnail_s3_key,
    }

    return metadata

def bedrock_converse(config, max_retries=3, retry_delay=1, image_s3_bucket=None, image_s3_key=None):
    inference_config = config.get("inferConfig")
    if not inference_config:
        inference_config = {"maxTokens": 500, "topP": 0.1, "temperature": 0.3}

    retries = 0
    while retries < max_retries:
        try:
            # Construct the message with text and image content
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": config["prompt"]
                        },
                    ]
                }
            ]

            if image_s3_bucket and image_s3_key:
                img_format = image_s3_key.split('.')[-1].lower()
                file_obj = s3.get_object(Bucket=image_s3_bucket, Key=image_s3_key)
                image_content = file_obj['Body'].read()
                messages[0]["content"].append({
                            "image": {
                                "format": img_format,
                                "source": {
                                    "bytes": image_content
                                },
                            }
                        })

            # Call Bedrock Converse
            if config.get("toolConfig"):
                response = bedrock.converse(
                    modelId=config["modelId"],
                    messages=messages,
                    inferenceConfig=inference_config,
                    toolConfig=config["toolConfig"]
                )
            else:
                response = bedrock.converse(
                    modelId=config["modelId"],
                    messages=messages,
                    inferenceConfig=inference_config,
                )
            #print(parse_converse_response(response))
            if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
                raise Exception(f"API request failed: {response['ResponseMetadata']['HTTPStatusCode']}")

            return response
        except Exception as ex:
            print(ex)
            retries += 1
            time.sleep(retry_delay)

    return None

def parse_converse_response(response):
    if not response:
        return None

    tool_use, txt_result = None, None
    contents = response.get("output",{}).get("message",{}).get("content",[])
    for c in contents:
        if "toolUse" in c:
            tool_use = c["toolUse"].get("input")
        elif "text" in c:
            txt_result = c["text"]
    
    if tool_use:
        return tool_use
    elif txt_result:
        return txt_result
    elif "content" in response:
        return response["content"]
    return response

def is_single_color_frame(task_id, index, thumbnail_s3_bucket, thumbnail_s3_key):
    config ={
              "name": "Thumbnail verfication",
              "modelId": MODEL_ID_IMAGE_UNDERSTANDING,
              "prompt": "Analyze the image if suitable to be used as a video thumbnail.",
              "toolConfig": {
                "tools": [
                  {
                    "toolSpec": {
                      "name": "tool_result",
                      "description": "Analyze the image and determine if it is suitable as a video thumbnail: it should not be a solid or blank screen, must have sufficient contrast and clarity.",
                      "inputSchema": {
                        "json": {
                          "type": "object",
                          "properties": {
                            "result": {
                              "type": "boolen",
                              "description": "If suitable to be used as a video thumbnail."
                            }
                          },
                          "required": [
                            "result"
                          ]
                        }
                      }
                    }
                  }
                ]
              },
              "inferConfig": {
                "maxTokens": 500,
                "topP": 0.1,
                "temperature": 0.7
              }
            }
    try:
        response = bedrock_converse(config=config, image_s3_bucket=thumbnail_s3_bucket, image_s3_key=thumbnail_s3_key)
        output = parse_converse_response(response)

        # Parse usage
        if "usage" in response:
            input_tokens = response["usage"]["inputTokens"]
            output_tokens = response["usage"]["outputTokens"]
            total_tokens = response["usage"]["totalTokens"]

            # store to the usage table
            update_usage_to_db(task_id, index, "thumbnail", MODEL_ID_IMAGE_UNDERSTANDING, input_tokens, output_tokens, total_tokens)

        return output is None or output.get("result") == True
    except Exception as ex:
        print(ex)
        return True

def update_usage_to_db(task_id, index, name, model_id, input_tokens, output_tokens, total_tokens):
    usage = {
        "id": f"{task_id}_{index}_{name}_thumbnail",
        "index": index,
        "type": "image_understanding",
        "name": name,
        "task_id": task_id,
        "model_id": model_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens
    }
    utils.dynamodb_table_upsert(DYNAMO_VIDEO_USAGE_TABLE, usage)    
    return usage