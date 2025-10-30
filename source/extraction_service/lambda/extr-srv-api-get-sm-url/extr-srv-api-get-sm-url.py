import json
import boto3
import os, time


SM_NOTEBOOK_INSTANCE_NAME = os.environ.get("SM_NOTEBOOK_INSTANCE_NAME")
sm = boto3.client("sagemaker")

def lambda_handler(event, context):
    response = sm.create_presigned_notebook_instance_url(
        NotebookInstanceName=SM_NOTEBOOK_INSTANCE_NAME
    )
    result = None
    if response:
        result = response.get("AuthorizedUrl")
    return {
            'statusCode': 200,
            'body': result
        }