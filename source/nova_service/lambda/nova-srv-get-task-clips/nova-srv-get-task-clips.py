import json
import boto3
import os
import utils

DYNAMO_VIDEO_TASK_TABLE = os.environ.get("DYNAMO_VIDEO_TASK_TABLE")
s3 = boto3.client('s3')

def lambda_handler(event, context):
    task_id = event.get("TaskId")
    if task_id is None:
        return {
            'statusCode': 400,
            'body': json.dumps('Require TaskId')
        }

    # Get video task from DB
    task = None
    try:
        task = utils.dynamodb_get_by_id(DYNAMO_VIDEO_TASK_TABLE, task_id)
    except Exception as ex:
        print(f'Task does not exist in {DYNAMO_VIDEO_TASK_TABLE}: {task_id}')

    if not task:
        return {
            'statusCode': 400,
            'body': json.dumps("Task doesn't exist")
        }

    s3_bucket = task["Request"]["Video"]["S3Object"]["Bucket"]
    s3_prefix = f"tasks/{task_id}/nova-mme/"

    result = {}
    # Get Nova MME S3 output files
    response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=s3_prefix)
    for obj in response.get('Contents', []):
        if "/nova-mme/search/" not in obj['Key'] and obj['Key'].endswith('.jsonl'):
            output_key = obj['Key']
            if output_key:
                #print("!!!", output_key)
                file_name = output_key.split(".")[-1].replace(".jsonl","")
                embed_option = file_name.replace("embedding_","")

                obj = s3.get_object(Bucket=s3_bucket, Key=output_key)
                lines = obj["Body"].iter_lines()
                for line in lines:
                    output = json.loads(line)
                    if output:
                        if embed_option not in result.keys():
                            result[embed_option] = []

                        result[embed_option].append({
                            "StartSec": output["segmentMetadata"]["segmentStartSeconds"],
                            "EndSec": output["segmentMetadata"]["segmentEndSeconds"]
                        })

    return {
        'statusCode': 200,
        'body': result
    }
