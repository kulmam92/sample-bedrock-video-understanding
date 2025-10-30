# Pre stack
S3_BUCKET_DATA_PREFIX='bedrock-mm'
COGNITO_NAME_PREFIX='bedrock-mm'
LAMBDA_NAME_PREFIX='bedrock-mm-'
COGNITO_NAME_PREFIX='bedrock-mm'
AGENTCORE_RUNTIME_NAME_PREFIX='bedrock_mm_video_understanding_agent'

S3_VECTOR_BUCKET_NAME='bedrock-mm-vector-bucket'
S3_VECTOR_INDEX_NAME='nova-mme-video-clip-1024'
S3_VECTOR_INDEX_NOVA_MME_FIXED = "nova-mme-video-async-1024"
S3_VECTOR_INDEX_TLABS = 'tlabs-video-1024'
EMBEDDING_DIM_DEFAULT='1024'

LAMBDA_LAYER_SOURCE_S3_KEY_SCENE_DETECT="layer/scenedetect_layer.zip"
LAMBDA_LAYER_SOURCE_S3_KEY_MOVIEPY="layer/moviepy_layer.zip"
LAMBDA_LAYER_SOURCE_S3_KEY_OPENCV="layer/opencv_layer.zip"
LAMBDA_LAYER_SOURCE_S3_KEY_BOTO3="layer/boto3_layer.zip"