"""
Роуты для авторизации
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from database import get_db_connection
from auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    username: str

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Вход в систему"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Находим пользователя
        cursor.execute(
            "SELECT id, username, password_hash FROM users WHERE username = %s",
            (request.username,)
        )
        user = cursor.fetchone()
        
        if not user or not verify_password(request.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль"
            )
        
        # Создаем токен
        access_token = create_access_token({
            "sub": user['username'],
            "user_id": user['id']
        })
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user_id=user['id'],
            username=user['username']
        )

@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """Регистрация нового пользователя"""
    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пароль должен быть не менее 6 символов"
        )
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (request.username,)
        )
        existing_user = cursor.fetchone()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким именем уже существует"
            )
        
        # Создаем пользователя
        password_hash = hash_password(request.password)
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
            (request.username, password_hash)
        )
        user_id = cursor.fetchone()['id']
        conn.commit()
        
        # Создаем токен
        access_token = create_access_token({
            "sub": request.username,
            "user_id": user_id
        })
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user_id=user_id,
            username=request.username
        )

@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Получить информацию о текущем пользователе"""
    return {
        "user_id": current_user["user_id"],
        "username": current_user["username"]
    }
