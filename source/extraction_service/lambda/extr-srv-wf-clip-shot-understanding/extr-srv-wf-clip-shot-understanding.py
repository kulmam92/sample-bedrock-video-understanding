import json
import boto3
import os
import utils
import time 

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
DYNAMO_VIDEO_SHOT_TABLE = os.environ.get("DYNAMO_VIDEO_SHOT_TABLE")
S3_BUCKET_DATA = os.environ.get("S3_BUCKET_DATA")

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime') 

def lambda_handler(event, context):
    if not event or "Key" not in event:
        return {
            'statusCode': 400,
            'body': f'Invalid request, {ex}'
        }

    s3_key = event.get("Key")
    s3_bucket = S3_BUCKET_DATA
    task_id, index, start_time, end_time = None, None, None, None

    try:
        arr = s3_key.split("/")
        task_id = arr[1]
        file_name = arr[-1]
        file_ext = file_name.split(".")[-1]

        arr2 = file_name.split("_")
        index = int(arr2[1])
        start_time = float(arr2[2])
        end_time = float(arr2[3].replace(f".{file_ext}",""))
    except Exception as ex:
        return {
            'statusCode': 400,
            'body': f'Invalid request, {ex}'
        }


    enabled, configs, outputs = None, None, None
    # Read task from DB
    task_db = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    if task_db: 
        enabled = task_db.get("Request",{}).get("ExtractionSetting", {}).get("Vision", {}).get("Shot", {}).get("Understanding",{}).get("Enabled")
        configs = task_db.get("Request",{}).get("ExtractionSetting", {}).get("Vision", {}).get("Shot", {}).get("Understanding",{}).get("PromptConfigs")

    if not enabled or enabled == False:
        return event

    # Invoke video understanding per prompt
    if configs:
        outputs = []
        for config in configs:
            response = bedrock_converse(config=config, s3_bucket=s3_bucket, s3_key=s3_key)
            output = parse_converse_response(response)
            if not output:
                output = response
            elif output.startswith('"') and output.endswith('"'):
                output = output[1:-1]
            outputs.append({
                "model_id": config["modelId"],
                "name": config["name"],
                "value": output
            })
        if outputs:
            # Store resutl to DB
            shot = update_shot_to_db(task_id, index, config["modelId"], outputs)

            # Store result to S3
            s3.put_object(Bucket=s3_bucket, Key=f'tasks/{task_id}/shot_outputs/output_{index}_{start_time}_{end_time}.json', Body=json.dumps(outputs))

    return {
        'statusCode': 200,
        'body': True
    }

def update_shot_to_db(task_id, index, model_id, outputs):
    shot_id = f'{task_id}_shot_{index}'
    shot = utils.dynamodb_get_by_id(DYNAMO_VIDEO_SHOT_TABLE, shot_id, key_name="id", sort_key_value=task_id, sort_key="task_id")
    if shot:
        shot["modelId"] = model_id
        shot["outputs"] = outputs
        utils.dynamodb_table_upsert(DYNAMO_VIDEO_SHOT_TABLE, shot)    
    return shot


def bedrock_converse(config, max_retries=3, retry_delay=1, s3_bucket=None, s3_key=None):
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

            if s3_bucket and s3_key:
                input_format = s3_key.split('.')[-1].lower()
                file_obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
                input_content = file_obj['Body'].read()

                if input_format in ["gif", "jpeg", "png", "webp"]:      
                    messages[0]["content"].append({
                                "image": {
                                    "format": input_format,
                                    "source": {
                                        "bytes": input_content
                                    },
                                }
                            })
                elif input_format in ["mp4"]:
                    messages[0]["content"].append({
                                "video": {
                                    "format": input_format,
                                    "source": {
                                        "bytes": input_content
                                    },
                                }
                            })
            
            if inference_config and "maxTokens" in inference_config:
                inference_config["maxTokens"] = int(inference_config["maxTokens"])

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
        return json.dumps(tool_use)
    elif txt_result:
        return json.dumps(txt_result)
    elif "content" in response:
        return json.dumps(response["content"])
    return json.dumps(response)
    