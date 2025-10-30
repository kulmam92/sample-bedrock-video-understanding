'''
"Source": mm_embedding | text_embedding | text,
'''
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
MODEL_ID = os.environ.get("MODEL_ID")
NOVA_S3_VECTOR_BUCKET = os.environ.get("NOVA_S3_VECTOR_BUCKET")
NOVA_S3_VECTOR_INDEX = os.environ.get("NOVA_S3_VECTOR_INDEX")
EMBEDDING_DIM = os.environ.get("EMBEDDING_DIM")

EMBEDDING_DIM = int(EMBEDDING_DIM) if EMBEDDING_DIM else 1024

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')
s3vectors = boto3.client('s3vectors') 

def lambda_handler(event, context):
    search_text = event.get("SearchText", "")
    page_size = event.get("PageSize", 10)
    from_index = event.get("FromIndex", 0)
    request_by = event.get("RequestBy")
    input_bytes = event.get("InputBytes", "")
    input_format = event.get("InputFormat", "")
    source = event.get("Source")
    input_type = event.get("InputType")
    TOP_K = event.get("TopK", 5)
    include_video_url = event.get("IncludeVideoUrl", True)

    embedding_options = event.get("EmbeddingOptions", ["audio-video", "video", "audio"])

    if search_text is None:
        search_text = ""
    if input_bytes is None:
        input_bytes = ""
    if len(search_text) > 0:
        search_text = search_text.strip()
    
    if search_text or input_bytes:
        input_embedding = None
        #s3_prefix_output = f'tasks/tlabs/search/{uuid.uuid4()}/'
        input_embedding = embed_input(input_type, search_text, input_bytes, input_format)
        if not input_embedding:
            return {
                'statusCode': 500,
                'body': 'Failed to generate input embedding'
            }
        clips = search_embedding_s3vectors(input_embedding, NOVA_S3_VECTOR_BUCKET, NOVA_S3_VECTOR_INDEX, TOP_K, embedding_options)

        result = []
        if clips:
            for clip in clips:
                tid = clip.get("metadata",{}).get("task_id")
                if tid:
                    task = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, tid, "Id")
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
    end_index = from_index + page_size if from_index + page_size < len(result) else len(result)
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

def embed_input(input_type, input_text, input_bytes, input_format, model_id=MODEL_ID):
    request_body = None
    if input_type == "text":
        request_body = {
            "schemaVersion": "nova-multimodal-embed-v1",
            "taskType": "SINGLE_EMBEDDING",
            "singleEmbeddingParams": {
                "embeddingPurpose": "VIDEO_RETRIEVAL",
                "embeddingDimension": EMBEDDING_DIM,
                "text": {
                    "truncationMode": "NONE",
                    "value": input_text,
                }
            }
        }

    elif input_type == "image" and input_bytes:
        request_body = {
            "schemaVersion": "nova-multimodal-embed-v1",
            "taskType": "SINGLE_EMBEDDING",
            "singleEmbeddingParams": {
                "embeddingPurpose": "VIDEO_RETRIEVAL",
                "embeddingDimension": EMBEDDING_DIM,
                "image": {
                    "detailLevel": "DOCUMENT_IMAGE",
                    "format": input_format,
                    "source": {"bytes": input_bytes},
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

def search_embedding_s3vectors(input_embedding, s3vector_bucket, s3vector_index, top_k, embedding_options):
    # Query vector index.
    response = s3vectors.query_vectors(
        vectorBucketName=s3vector_bucket,
        indexName=s3vector_index,
        queryVector={"float32": input_embedding}, 
        topK=top_k, 
        returnDistance=True,
        returnMetadata=True,
        filter={"embeddingOption": {"$in": embedding_options}}
    )

    return response["vectors"]