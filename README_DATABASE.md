# Mazmundama - Database & S3 Integration

## Инициализация системы

### 1. Установка зависимостей
```bash
pip install psycopg2-binary boto3 passlib python-jose
```

### 2. Настройка .env
Убедитесь что `.env` содержит:
```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mazmundama_final

# S3 Storage
S3_ENDPOINT=https://mazmundama.object.pscloud.io
S3_ACCESS_KEY=85KY53ZHS2BK2S2I1O4A
S3_SECRET_KEY=0tOOgQo6rTTYbPknpPp87FOoS7QuO5gAFDJEB6kC
S3_BUCKET_NAME=mazmundama

# JWT Secret
JWT_SECRET_KEY=mazmundama_secret_key_change_in_production_12345
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=43200
```

### 3. Инициализация БД
```bash
python init_db.py
```

Это создаст:
- Таблицы в PostgreSQL (users, books, translations, translation_versions)
- Bucket в S3
- Первого пользователя: `mazmundama` / `mazmundama123`

## Архитектура

### База данных (PostgreSQL)
- **users** - пользователи системы
- **books** - информация о загруженных книгах
- **translations** - текущие переводы предложений
- **translation_versions** - история версий переводов

### S3 Storage
- Хранение DOCX файлов книг
- Структура: `users/{user_id}/books/{filename}`

## API Endpoints

### Авторизация (/api/auth)
```bash
# Вход
POST /api/auth/login
Body: {"username": "mazmundama", "password": "mazmundama123"}

# Регистрация
POST /api/auth/register
Body: {"username": "newuser", "password": "password123"}

# Информация о пользователе
GET /api/auth/me
Headers: Authorization: Bearer {token}
```

### Книги (/api/books)
```bash
# Загрузка книги
POST /api/books/upload
Headers: Authorization: Bearer {token}
Body: multipart/form-data with file

# Список книг
GET /api/books/list
Headers: Authorization: Bearer {token}

# Получить книгу с переводами
GET /api/books/{book_id}
Headers: Authorization: Bearer {token}

# Сохранить перевод
POST /api/books/translation/save
Headers: Authorization: Bearer {token}
Body: {
  "book_id": 1,
  "page_number": 1,
  "sentence_id": "sent_1_0",
  "original_text": "Hello world",
  "translation": "Сәлем әлем",
  "model": "chatgpt"
}

# История версий перевода
GET /api/books/translation/{book_id}/history?sentence_id=sent_1_0
Headers: Authorization: Bearer {token}

# Одобрить перевод
POST /api/books/translation/approve
Headers: Authorization: Bearer {token}
Body: {"book_id": 1, "sentence_id": "sent_1_0"}

# Удалить книгу
DELETE /api/books/{book_id}
Headers: Authorization: Bearer {token}
```

## Запуск сервера
```bash
python main.py
```

Сервер запустится на http://127.0.0.1:8080

## Тестирование

### 1. Вход в систему
```bash
curl -X POST http://127.0.0.1:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "mazmundama", "password": "mazmundama123"}'
```

Ответ:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user_id": 1,
  "username": "mazmundama"
}
```

### 2. Загрузка книги
```bash
curl -X POST http://127.0.0.1:8080/api/books/upload \
  -H "Authorization: Bearer {your_token}" \
  -F "file=@path/to/book.docx"
```

### 3. Работа с переводами
Используйте полученный `book_id` для сохранения переводов через endpoint `/api/books/translation/save`

## Безопасность
- Все endpoints книг защищены JWT авторизацией
- Пароли хешируются с помощью SHA256
- Токены действительны 30 дней (настраивается в .env)
- Каждый пользователь видит только свои книги

## Следующие шаги
- Обновить frontend для работы с авторизацией
- Добавить страницу входа/регистрации
- Интегрировать сохранение переводов в БД
- Добавить загрузку истории переводов при открытии книги
