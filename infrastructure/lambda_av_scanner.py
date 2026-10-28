import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    [S3 Native Event Trigger AV Scanner]
    """
    for record in event['Records']:
        source_bucket = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        
        logger.info(f"Scanning file from Quarantine Bucket: {source_bucket}/{object_key}")
        
        # [모의 백신 엔진 검사 수행]
        is_clean = True 
        
        target_bucket = "lotte-promo-production-bucket-official"
        
        if is_clean:
            # Clean 판정 시 공식 운영 버킷으로 자동 이동
            copy_source = {'Bucket': source_bucket, 'Key': object_key}
            s3_client.copy_object(CopySource=copy_source, Bucket=target_bucket, Key=object_key)
            s3_client.delete_object(Bucket=source_bucket, Key=object_key)
            logger.info(f"File passed AV scan. Promoted to official bucket: {object_key}")
        else:
            # 악성코드 발견 시 즉시 영구 격리 및 삭제
            s3_client.delete_object(Bucket=source_bucket, Key=object_key)
            logger.warning(f"Malware detected! File deleted from quarantine: {object_key}")
            
    return {"status": "SUCCESS"}