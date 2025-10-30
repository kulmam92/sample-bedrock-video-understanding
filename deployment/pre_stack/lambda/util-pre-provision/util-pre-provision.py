import os
import json
import boto3
import subprocess, shutil, sys, zipfile

iam = boto3.client('iam')
s3 = boto3.client('s3')
s3vectors = boto3.client('s3vectors') 

def on_event(event, context):
  print(event)
  request_type = event['RequestType']
  if request_type == 'Create': return on_create(event)
  if request_type == 'Post': return on_post(event)
  if request_type == 'Delete': return on_delete(event)
  raise Exception("Invalid request type: %s" % request_type)

def on_create(event):
    layers = event.get("Layers")
    if layers:
        for layer in layers:
            layer_name = layer.get("name")
            layer_packages = layer.get("packages")
            s3_bucket = layer.get("s3_bucket")
            s3_key = layer.get("s3_key")
            create_layer_zip(layer_name, layer_packages, s3_bucket, s3_key)

    s3_vectors = event.get("S3Vectors")
    if s3_vectors:
        for v in s3_vectors:
            create_s3_vector_index_bucket(v["BucketName"], v["IndexName"], v["IndexDim"])


def create_layer_zip(name, packages, s3_bucket, s3_key):
    folder_name = f'{name.replace("-","")}_layer'
    zip_file_name = s3_key.split('/')[-1]
    print("!!!",folder_name, zip_file_name)

    os.makedirs(f'/tmp/{folder_name}/python', exist_ok=True)
    shutil.rmtree(f'/tmp/{folder_name}/')
    for p in packages:
        subprocess.call(f'pip install {p["name"]}=={p["version"]} -t /tmp/{folder_name}/python/ --no-cache-dir'.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.chdir(f'/tmp/{folder_name}/')

    subprocess.call('touch ./python/__init__.py'.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    zip_folder(f'/tmp/{folder_name}',f'/tmp/{folder_name}/{zip_file_name}')

    s3.upload_file(f'/tmp/{folder_name}/{zip_file_name}', s3_bucket, s3_key)
    print("!!! to S3",f'/tmp/{folder_name}/{zip_file_name}', s3_bucket, s3_key)
    
def zip_folder(folder_path, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, rel_path)

def create_s3_vector_index_bucket(bucket_name, index_name, index_dim):
    # create bucket
    try:
        s3vectors.create_vector_bucket(vectorBucketName=bucket_name)
        print(f"Vector bucket '{bucket_name}' created successfully.")
    except Exception as ex:
        print(f"Failed to create s3 vector bucket: {bucket_name}", ex)

    # create index
    try:
        # Create an index in the vector store
        index_dim = 1024 if not index_dim else int(index_dim)
        distance_metric = 'cosine' # or 'euclidean'

        s3vectors.create_index(
            vectorBucketName=bucket_name,
            indexName=index_name,
            dataType='float32',  # Common data type for vector embeddings
            dimension=index_dim,
            distanceMetric=distance_metric
        )
        print(f"Vector index '{index_name}' created successfully in bucket '{bucket_name}'.")

    except Exception as ex:
        print(f"Failed to create s3 index {index_name} bucket: {bucket_name}", ex)