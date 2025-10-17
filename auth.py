from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_EXPIRATION_MINUTES = int(os.getenv('JWT_EXPIRATION_MINUTES', 43200))  # 30 дней по умолчанию

# Настройка хеширования паролей (используем SHA256 вместо bcrypt из-за проблем совместимости)
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# Настройка Bearer token
security = HTTPBearer()

def hash_password(password: str) -> str:
    """Хеширует пароль"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    """
    Создает JWT токен
    
    Args:
        data: данные для кодирования в токен (обычно {"sub": username, "user_id": id})
    
    Returns:
        JWT токен
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """
    Декодирует JWT токен
    
    Args:
        token: JWT токен
        
    Returns:
        Декодированные данные из токена
        
    Raises:
        HTTPException: если токен невалиден
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен авторизации",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency для получения текущего пользователя из токена
    
    Returns:
        Данные пользователя из токена
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    username = payload.get("sub")
    user_id = payload.get("user_id")
    
    if username is None or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось определить пользователя",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {"username": username, "user_id": user_id}
