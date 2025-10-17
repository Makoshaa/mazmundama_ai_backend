"""
Скрипт инициализации базы данных
Создает таблицы и первого пользователя
"""

from database import init_database, get_db_connection
from auth import hash_password
from s3_storage import ensure_bucket_exists

def create_initial_user():
    """Создает первого пользователя mazmundama"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute("SELECT id FROM users WHERE username = %s", ('mazmundama',))
        existing_user = cursor.fetchone()
        
        if existing_user:
            print("[WARNING] User 'mazmundama' already exists")
            return
        
        # Создаем пользователя
        password_hash = hash_password('mazmundama123')
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
            ('mazmundama', password_hash)
        )
        user_id = cursor.fetchone()['id']
        
        conn.commit()
        print(f"[OK] User 'mazmundama' created (ID: {user_id})")
        print(f"   Username: mazmundama")
        print(f"   Password: mazmundama123")

def main():
    """Главная функция инициализации"""
    print("\n=== Initialization of Mazmundama system ===\n")
    
    # Шаг 1: Инициализация БД
    print("[1] Creating tables in PostgreSQL...")
    try:
        init_database()
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        return
    
    # Шаг 2: Создание bucket в S3
    print("\n[2] Checking S3 bucket...")
    try:
        ensure_bucket_exists()
    except Exception as e:
        print(f"[WARNING] S3 error: {e}")
        print("   (Continuing without S3)")
    
    # Шаг 3: Создание первого пользователя
    print("\n[3] Creating initial user...")
    try:
        create_initial_user()
    except Exception as e:
        print(f"[ERROR] User creation failed: {e}")
        return
    
    print("\n[OK] Initialization completed successfully!")
    print("\n=== System is ready ===\n")

if __name__ == "__main__":
    main()
