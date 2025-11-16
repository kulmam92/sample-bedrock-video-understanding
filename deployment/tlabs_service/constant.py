API_NAME_PREFIX = 'bedrock_mm_tlabs_service'
DYNAMO_VIDEO_TASK_TABLE = "bedrock_mm_tlabs_video_task"
DYNAMO_VIDEO_USAGE_TABLE="bedrock_mm_usage"

S3_BUCKET_NAME_PREFIX_MM = 'bedrock-mm-tlabs'
S3_VECTOR_BUCKET_TLABS = 'bedrock-mm-vector-bucket'
S3_PRE_SIGNED_URL_EXPIRY_S = "3600"
VIDEO_SAMPLE_S3_PREFIX = "video_frame_"
VIDEO_UPLOAD_S3_PREFIX = 'upload'

LAMBDA_LAYER_SOURCE_S3_KEY_BOTO3 = "layer/boto3_layer.zip"
LAMBDA_LAYER_SOURCE_S3_KEY_MOVIEPY = "layer/moviepy_layer.zip"
LAMBDA_NAME_PREFIX = 'bedrock-mm-'

MODEL_ID_IMAGE_UNDERSTANDING="amazon.nova-lite-v1:0"

MODEL_ID_TLAB_27='twelvelabs.marengo-embed-2-7-v1:0'
MODEL_ID_TLAB_30='twelvelabs.marengo-embed-3-0-v1:0'
TLABS_S3_VECTOR_INDEX_27='tlabs-video-1024'
TLABS_S3_VECTOR_INDEX_30='tlabs-video-512'