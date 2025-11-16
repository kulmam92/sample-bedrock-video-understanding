import json
import boto3
import os
import re
from urllib.parse import urlparse
import utils
import uuid
import time
import base64

S3_PRESIGNED_URL_EXPIRY_S = os.environ.get("S3_PRESIGNED_URL_EXPIRY_S", 3600) # Default 1 hour 
S3_BUCKET_DATA = os.environ.get("S3_BUCKET_DATA")

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
MODEL_ID_TLAB_27 = os.environ.get("MODEL_ID_TLAB_27")
MODEL_ID_TLAB_30 = os.environ.get("MODEL_ID_TLAB_30")
TLABS_S3_VECTOR_BUCKET = os.environ.get("TLABS_S3_VECTOR_BUCKET")
TLABS_S3_VECTOR_INDEX_27 = os.environ.get("TLABS_S3_VECTOR_INDEX_27")
TLABS_S3_VECTOR_INDEX_30 = os.environ.get("TLABS_S3_VECTOR_INDEX_30")

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')
s3vectors = boto3.client('s3vectors') 

MODEL_ID_TLAB, TLABS_S3_VECTOR_INDEX = None, None

def lambda_handler(event, context):
    search_text = event.get("SearchText", "")
    page_size = event.get("PageSize", 10)
    from_index = event.get("FromIndex", 0)
    request_by = event.get("RequestBy")
    input_bytes = event.get("InputBytes", "")
    source = event.get("Source")
    input_type = event.get("InputType")
    top_k = event.get("TopK")
    include_video_url = event.get("IncludeVideoUrl", True)
    task_type = event.get("TaskType")

    embedding_options = event.get("EmbeddingOptions")
    if not embedding_options:
        embedding_options = ["visual-text", "visual-image", "audio"] if task_type == "marengo27" else ["visual", "audio", "transcription"]
    
    if search_text is None:
        search_text = ""
    if input_bytes is None:
        input_bytes = ""
    if len(search_text) > 0:
        search_text = search_text.strip()

    MODEL_ID_TLAB = MODEL_ID_TLAB_30 if task_type == "marengo30" else MODEL_ID_TLAB_27
    TLABS_S3_VECTOR_INDEX = TLABS_S3_VECTOR_INDEX_30 if task_type == "marengo30" else TLABS_S3_VECTOR_INDEX_27

    # Get Tasks by RequestBy
    db_tasks = utils.get_tasks_by_requestby(
                table_name=DYNAMO_VIDEO_TASK_TABLE, 
                request_by=request_by
            )

    if db_tasks is None or len(db_tasks) == 0:
        return {
            'statusCode': 200,
            'body': []
        }

    tasks = {}
    for task in db_tasks:
        tasks[task["Id"]] = task
    
    if search_text or input_bytes:
        input_embedding = None
        s3_prefix_output = f'tasks/tlabs/search/{uuid.uuid4()}/'
        input_embedding = get_embedding(input_type, search_text, input_bytes, MODEL_ID_TLAB, task_type)
        if not input_embedding:
            return {
                'statusCode': 500,
                'body': 'Failed to generate input embedding'
            }
        clips = search_embedding_s3vectors(input_embedding, TLABS_S3_VECTOR_BUCKET, TLABS_S3_VECTOR_INDEX, embedding_options)
        #return clips
        result = []
        if clips:
            for clip in clips:
                tid = clip.get("metadata",{}).get("task_id")
                if tid:
                    task =  tasks.get(tid)
                    if task:
                        item = {
                            "TaskId": tid,
                            "StartSec": clip["metadata"].get("startSec"),
                            "EndSec": clip["metadata"].get("endSec"),
                            "EmbeddingOption": clip["metadata"].get("embeddingOption"),
                            "Distance": clip["distance"],
                            "TaskName": task["Request"].get("FileName"),
                            "FileName": task["Request"]["FileName"],
                            "RequestTs": task["RequestTs"],
                            "Status": task["Status"],
                            "S3Bucket": task.get("Request",{}).get("Video",{}).get("S3Object",{}).get("Bucket"),
                            "S3Key": task.get("Request",{}).get("Video",{}).get("S3Object",{}).get("Key")
                        } 
                        result.append(item)    
                
    # Pagination
    from_index = from_index if from_index > 0 else 0
    end_index = from_index + page_size if from_index + page_size < len(result) else len(tasks)
    result = result[from_index: end_index]

    # Get S3 presigned URL
    if include_video_url:
        for item in result:
            s3_bucket = item.get("S3Bucket")
            s3_key = item.get("S3Key")
            if s3_bucket and s3_key:
                item["VideoUrl"] = s3.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': s3_bucket, 'Key': s3_key},
                        ExpiresIn=S3_PRESIGNED_URL_EXPIRY_S
                    )

    return {
        'statusCode': 200,
        'body': result
    }

def wait_for_output_file(s3_bucket, s3_prefix, invocation_arn):
    # Wait until task complete
    status = None
    while status not in ["Completed", "Failed", "Expired"]:
        response = bedrock.get_async_invoke(invocationArn=invocation_arn)
        status = response['status']
        time.sleep(2)

    # List objects in the prefix
    response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=f'{s3_prefix}')

    # Look for output.json
    data = []
    output_key = None
    for obj in response.get('Contents', []):
        if obj['Key'].endswith('output.json'):
            output_key = obj['Key']
            if output_key:
                #print("!!!", output_key)
                obj = s3.get_object(Bucket=s3_bucket, Key=output_key)
                content = obj['Body'].read().decode('utf-8')
                return json.loads(content).get("data")[0].get("embedding")
    return None

def search_embedding_s3vectors(input_embedding, s3vector_bucket, s3vector_index, embedding_options):
    # Query vector index.
    response = s3vectors.query_vectors(
        vectorBucketName=s3vector_bucket,
        indexName=s3vector_index,
        queryVector={"float32": input_embedding}, 
        topK=5, 
        returnDistance=True,
        returnMetadata=True,
        filter={"embeddingOption": {"$in": embedding_options}}
    )

    return response["vectors"]

# create embedding using 12labs SaaS API
def get_embedding(input_type, search_text, input_bytes, model_id, task_type):
    model_input = None
    if input_type == "text":
        if task_type == "marengo27":
            model_input = {
                "inputType": "text",
                "inputText": search_text
            }
        else:
            model_input = {
                "inputType": "text",
                "text": {
                    "inputText": search_text
                }
            }
    elif input_type == "image":
        if task_type == "marengo27":
            model_input = {
                "inputType": "image",
                "mediaSource": {
                    "base64String": input_bytes
                }
            }
        else:
            model_input = {
                "inputType": "image",
                "image": {
                    "mediaSource": {
                        "base64String": input_bytes
                    }
                }
            }

    response = bedrock.invoke_model(
        modelId=f'us.{model_id}',
        body=json.dumps(model_input)
    )
    response_body = json.loads(response['body'].read().decode('utf-8'))
    embedding = response_body.get("data",[{}])[0].get("embedding")
    
    return embedding