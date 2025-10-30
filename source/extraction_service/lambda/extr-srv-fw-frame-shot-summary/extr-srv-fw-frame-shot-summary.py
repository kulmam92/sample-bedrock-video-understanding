import json
import boto3
import re
import numbers,decimal
from boto3.dynamodb.conditions import Key
import os
import time

DYNAMO_VIDEO_ANALYSIS_TABLE = os.environ.get("DYNAMO_VIDEO_ANALYSIS_TABLE")

INFERENCE_CONFIG_DEFAULT = {"maxTokens": 500, "topP": 0.1, "temperature": 0.3}

bedrock_runtime_client = boto3.client(service_name='bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

video_analysis_table = dynamodb.Table(DYNAMO_VIDEO_ANALYSIS_TABLE)

def lambda_handler(event, context):
    if event is None or "Error" in event or "Request" not in event or "Key" not in event:
        return {
            "Error": "Invalid Request"
        }
    task_id = event["Request"].get("TaskId")
    s3_bucket = event["MetaData"]["VideoFrameS3"]["S3Bucket"]
    s3_key = event.get("Key")

    shot_config = event.get("Request",{}).get("AnalysisSetting", {}).get("Shot")
    if not shot_config:
        return {
            "Error": "Missing shot analysis configuration."
        }

    # Read JSON from S3
    shot = None
    try:
        shot = json.loads(s3.get_object(Bucket=s3_bucket, Key=s3_key)['Body'].read().decode('utf-8'))
    except Exception as ex:
        print("Failed to read Shot JSON from S3:", s3_bucket, s3_key)
        return event

    # Shot custom output
    outputs = None
    if shot_config.get("PromptConfigs"):
        outputs = []
        for config in shot_config["PromptConfigs"]:
            outputs.append({
                "name": config.get("name"),
                "model_id": config["modelId"],
                "result": call_llm(config, shot.get("frames"))
            })
        print(outputs)
        if outputs:
            shot["outputs"] = outputs
        s3.put_object(Bucket=s3_bucket, 
            Key=s3_key, 
            Body=json.dumps(shot), 
            ContentType='application/json'
        )

    # Update DB record: including summary
    db_shot = convert_dynamo_to_json_format(video_analysis_table.get_item(Key={"id": shot["id"], "task_id": task_id})["Item"])
    if outputs:
        db_shot["outputs"] = outputs
    resposne = video_analysis_table.put_item(Item=convert_to_dynamo_format(db_shot))

    #event["shots"] = shots
    return event

def call_llm(config, frames):
    if not config or not frames:
        return None

    # Construct messages using frame summary
    messages = [
        {
            "role": "user",
            "content": []
        }
    ]
    if config.get("Prompt"):
        messages[0]["content"].append({"text": config["prompt"]})
    for f in frames:
        s3_bucket = f.get("s3_bucket")
        s3_key = f.get("s3_key")
        if s3_bucket and s3_key:
            file_obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
            image_content = file_obj['Body'].read()
            messages[0]["content"].append({
                        "image": {
                            "format": "png",
                            "source": {
                                "bytes": image_content
                            },
                        }
                    })

    response = bedrock_converse(messages=messages, model_id=config["modelId"], tool_config=config.get("toolConfig"), inference_config=config.get("inferConfig"))
    return parse_converse_response(response)

def bedrock_converse(messages, model_id, max_retries=3, retry_delay=1, inference_config=INFERENCE_CONFIG_DEFAULT, tool_config=None):
    retries = 0
    while retries < max_retries:
        try:
            # Call Bedrock Converse
            if tool_config:
                response = bedrock_runtime_client.converse(
                    modelId=model_id,
                    messages=messages,
                    inferenceConfig=inference_config,
                    toolConfig=tool_config
                )
            else:
                response = bedrock_runtime_client.converse(
                    modelId=model_id,
                    messages=messages,
                    inferenceConfig=inference_config,
                )
            if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
                raise Exception(f"API request failed: {response["ResponseMetadata"]['HTTPStatusCode']}")
 
            
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