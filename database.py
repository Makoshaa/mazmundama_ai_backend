import psycopg2
from psycopg2.extras import RealDictCursor
import os
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

@contextmanager
def get_db_connection():
    """Context manager для безопасной работы с подключением к БД"""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_database():
    """Инициализация базы данных - создание таблиц"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица книг
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(255),
                s3_key VARCHAR(500) NOT NULL,
                total_pages INTEGER DEFAULT 0,
                total_sentences INTEGER DEFAULT 0,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, s3_key)
            )
        """)
        
        # Добавляем поля если их нет (миграция)
        cursor.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='books' AND column_name='total_pages') THEN
                    ALTER TABLE books ADD COLUMN total_pages INTEGER DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='books' AND column_name='total_sentences') THEN
                    ALTER TABLE books ADD COLUMN total_sentences INTEGER DEFAULT 0;
                END IF;
            END $$;
        """)
        
        # Таблица страниц книги (обработанный HTML)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS book_pages (
                id SERIAL PRIMARY KEY,
                book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
                page_number INTEGER NOT NULL,
                html_content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, page_number)
            )
        """)
        
        # Таблица предложений и переводов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                id SERIAL PRIMARY KEY,
                book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
                page_number INTEGER NOT NULL,
                sentence_id VARCHAR(100) NOT NULL,
                original_text TEXT NOT NULL,
                current_translation TEXT,
                is_approved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, sentence_id)
            )
        """)
        
        # Таблица версий переводов (история)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translation_versions (
                id SERIAL PRIMARY KEY,
                translation_id INTEGER REFERENCES translations(id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                model VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индексы для производительности
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_books_user_id ON books(user_id);
            CREATE INDEX IF NOT EXISTS idx_book_pages_book_id ON book_pages(book_id);
            CREATE INDEX IF NOT EXISTS idx_translations_book_id ON translations(book_id);
            CREATE INDEX IF NOT EXISTS idx_translation_versions_translation_id 
                ON translation_versions(translation_id);
        """)
        
        conn.commit()
        print("[OK] Database initialized successfully!")

if __name__ == "__main__":
    init_database()
