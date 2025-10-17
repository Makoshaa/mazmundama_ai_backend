import boto3
from botocore.client import Config
import os
from dotenv import load_dotenv

load_dotenv()

S3_ENDPOINT = os.getenv('S3_ENDPOINT')
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'mazmundama')

# Создаем несколько вариантов S3 клиента для совместимости

# Общая конфигурация для обхода ошибок checksum на S3-совместимых сторажах
common_checksum_kwargs = {
    'request_checksum_calculation': 'when_required',
    'response_checksum_validation': 'when_required'
}

# Вариант 1: С отключенным payload signing (решает проблему XAmzContentSHA256Mismatch)
s3_client_unsigned = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name='us-east-1',
    config=Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path', 'payload_signing_enabled': False},
        **common_checksum_kwargs
    )
)

# Вариант 2: Со стандартными настройками
s3_client_auto = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name='us-east-1',
    config=Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'},
        **common_checksum_kwargs
    )
)

# Вариант 3: С signature v4 и path-style addressing
s3_client_v4 = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name='us-east-1',
    config=Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'},
        **common_checksum_kwargs
    )
)

# Используем unsigned вариант по умолчанию (самый совместимый)
s3_client = s3_client_unsigned

def ensure_bucket_exists():
    """Проверяет существование bucket и создает его если нужно"""
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
        print(f"[OK] Bucket '{S3_BUCKET_NAME}' exists")
    except:
        try:
            s3_client.create_bucket(Bucket=S3_BUCKET_NAME)
            print(f"[OK] Bucket '{S3_BUCKET_NAME}' created")
        except Exception as e:
            print(f"[ERROR] Bucket creation failed: {e}")

def upload_file_to_s3(file_content: bytes, s3_key: str, content_type: str = 'application/octet-stream') -> str:
    """
    Загружает файл в S3
    
    Args:
        file_content: содержимое файла в байтах
        s3_key: путь к файлу в S3 (например: "users/1/books/filename.docx")
        content_type: MIME-тип файла
        
    Returns:
        S3 key загруженного файла
    """
    # Пробуем сначала с unsigned клиентом (без payload signing)
    try:
        s3_client_unsigned.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type
        )
        return s3_key
    except Exception as e1:
        # Если не получилось, пробуем с автоматическим клиентом
        print(f"[S3] Unsigned client failed, trying auto: {str(e1)}")
        try:
            s3_client_auto.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type
            )
            print(f"[S3] Upload successful with auto client")
            return s3_key
        except Exception as e2:
            # Последняя попытка с v4 клиентом
            print(f"[S3] Auto client failed, trying v4: {str(e2)}")
            try:
                s3_client_v4.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=s3_key,
                    Body=file_content,
                    ContentType=content_type
                )
                print(f"[S3] Upload successful with v4 client")
                return s3_key
            except Exception as e3:
                import traceback
                error_details = traceback.format_exc()
                print(f"[S3 ERROR] All clients failed:")
                print(error_details)
                raise Exception(f"Ошибка загрузки файла в S3: {str(e3)}")

def download_file_from_s3(s3_key: str) -> bytes:
    """
    Скачивает файл из S3
    
    Args:
        s3_key: путь к файлу в S3
        
    Returns:
        Содержимое файла в байтах
    """
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return response['Body'].read()
    except Exception as e:
        raise Exception(f"Ошибка скачивания файла из S3: {str(e)}")

def delete_file_from_s3(s3_key: str) -> bool:
    """
    Удаляет файл из S3
    
    Args:
        s3_key: путь к файлу в S3
        
    Returns:
        True если успешно удалено
    """
    try:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return True
    except Exception as e:
        print(f"Ошибка удаления файла из S3: {str(e)}")
        return False

def list_user_files(user_id: int) -> list:
    """
    Список файлов пользователя в S3
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Список ключей файлов
    """
    try:
        prefix = f"users/{user_id}/books/"
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=prefix
        )
        
        if 'Contents' in response:
            return [obj['Key'] for obj in response['Contents']]
        return []
    except Exception as e:
        print(f"Ошибка получения списка файлов: {str(e)}")
        return []

if __name__ == "__main__":
    ensure_bucket_exists()
