# PreStack
COGNITO_NAME_PREFIX = "bedrock_mm_user_pool"
S3_VECTOR_BUCKET_NOVA = "bedrock-mm-vector-bucket"
S3_VECTOR_INDEX_NOVA = "nova-mme-video-async-1024"
S3_VECTOR_INDEX_DIM_NOVA = "1024"

# Main Stack
API_NAME_PREFIX = 'bedrock-mm-nova-mme'
DYNAMO_VIDEO_TASK_TABLE = "bedrock_mm_nova_video_task"

LAMBDA_NAME_PREFIX='bedrock-mm-'

S3_BUCKET_NAME_PREFIX_MM = 'bedrock-mm-nova-mme'
S3_PRE_SIGNED_URL_EXPIRY_S = "3600"
VIDEO_SAMPLE_S3_PREFIX = "video_frame_"
VIDEO_UPLOAD_S3_PREFIX = 'upload'

LAMBDA_LAYER_SOURCE_S3_KEY_BOTO3 = "layer/boto3_layer.zip"
LAMBDA_LAYER_SOURCE_S3_KEY_MOVIEPY = "layer/moviepy_layer.zip"

MODEL_ID_IMAGE_UNDERSTANDING="amazon.nova-lite-v1:0"
MODEL_ID_BEDROCK_MME='amazon.nova-2-multimodal-embeddings-v1:0'
