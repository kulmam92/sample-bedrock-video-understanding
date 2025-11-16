import json
import boto3
import os
import time 
import utils
import base64

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")

MME_MODEL_ID = os.environ.get("MME_MODEL_ID")
S3_VECTOR_BUCKET = os.environ.get("S3_VECTOR_BUCKET")
S3_VECTOR_INDEX = os.environ.get("S3_VECTOR_INDEX")
S3_BUCKET_DATA = os.environ.get("S3_BUCKET_DATA")
EMBEDDING_DIM = os.environ.get("EMBEDDING_DIM")
EMBEDDING_DIM = int(EMBEDDING_DIM) if EMBEDDING_DIM else 1024
DYNAMO_VIDEO_USAGE_TABLE = os.environ.get("DYNAMO_VIDEO_USAGE_TABLE")

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')
s3vectors = boto3.client('s3vectors') 

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

    enabled = None
    # Read task from DB
    task_db = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    if task_db: 
        enabled = task_db.get("Request",{}).get("ExtractionSetting", {}).get("Vision", {}).get("Shot", {}).get("Embedding",{}).get("Enabled")
    
    if not enabled or enabled == False:
        return event

    model_id = task_db.get("Request",{}).get("ExtractionSetting", {}).get("Vision", {}).get("Shot", {}).get("Embedding",{}).get("ModelId")
    if not model_id:
        model_id = MME_MODEL_ID

    # Generate embedding for the video clip
    vector_entry = None
    embedding = generate_embedding(s3_bucket, s3_key, model_id = model_id)
    if embedding:
        # store usage
        update_usage_to_db(task_id, index, "video segment embedding", model_id, end_time-start_time)

        embed_type = "AUDIO_VIDEO"

        # Store embedding as JSON to S3
        embed_json = {
            "index": index,
            "embeddingMode": embed_type,
            "startSec": start_time, 
            "endSec": end_time,
            "embedding": embedding
        }
        s3.put_object(
            Bucket=s3_bucket, 
            Key=f'tasks/{task_id}/shot_vector/{embed_type}_{index}.json', 
            Body=json.dumps(embed_json)
        )

        # Store to S3 vector
        vector_entry = {
                "key": f'{task_id}_{embed_type}_{index}',
                "data": {"float32": embedding},
                "metadata": {
                    "index": index,
                    "task_id": task_id, 
                    "embeddingOption": embed_type, 
                    "startSec": start_time, 
                    "endSec": end_time
                }
            }

        s3vectors.put_vectors(
                vectorBucketName=S3_VECTOR_BUCKET,   
                indexName=S3_VECTOR_INDEX,   
                vectors=[vector_entry]
            )

    return {
        'statusCode': 200,
        'body': True
    }

def generate_embedding(s3_bucket, s3_key, model_id):
    try:
        video_format = s3_key.split(".")[-1].lower()

        # Get file bytes in base64
        response = s3.get_object(Bucket=s3_bucket, Key=s3_key)
        file_bytes = response["Body"].read()
        encoded = base64.b64encode(file_bytes).decode("utf-8")

        request_body = {
            "schemaVersion": "nova-multimodal-embed-v1",
            "taskType": "SINGLE_EMBEDDING",
            "singleEmbeddingParams": {
                "embeddingPurpose": "GENERIC_INDEX",
                "embeddingDimension": EMBEDDING_DIM,
                "video": {
                    "format": video_format,
                    "source": {"bytes": encoded},
                    "embeddingMode": "AUDIO_VIDEO_COMBINED"
                }
            }
        }


        # Invoke the Nova Embeddings model.
        response = bedrock.invoke_model(
            body=json.dumps(request_body),
            modelId=model_id,
            accept="application/json",
            contentType="application/json",
        )

        # Decode the response body.
        response_body = json.loads(response.get("body").read())
        response_metadata = response["ResponseMetadata"]
        return response_body["embeddings"][0]["embedding"]
    except Exception as ex:
        print(ex)
        return None

def update_usage_to_db(task_id, index, name, model_id, duration_s):
    usage = {
        "id": f"{task_id}_{index}_shot",
        "index": index,
        "type": "nova_mme_video",
        "name": name,
        "task_id": task_id,
        "model_id": model_id,
        "duration_s": duration_s
    }
    utils.dynamodb_table_upsert(DYNAMO_VIDEO_USAGE_TABLE, usage)    
    return usage