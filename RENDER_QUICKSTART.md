# Быстрый старт: Деплой на Render

## Краткая инструкция

### 1. Подготовка (локально)
```bash
# Убедитесь, что все файлы закоммичены
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

### 2. Создание PostgreSQL БД на Render
1. Перейти на https://dashboard.render.com
2. New + → PostgreSQL
3. Name: `mazmundama-db`, Database: `mazmundama`
4. Создать и скопировать **Internal Database URL**

### 3. Создание Web Service
1. New + → Blueprint (если есть render.yaml)
   ИЛИ
   New + → Web Service (ручная настройка)
2. Подключить GitHub репозиторий
3. Настройки:
   - Root Directory: `backend`
   - Build Command: `bash build.sh`
   - Start Command: `bash start.sh`

### 4. Настройка переменных окружения

**Обязательные:**
```env
DATABASE_URL=<из_шага_2>
JWT_SECRET_KEY=<сгенерировать_случайную_строку>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**API ключи:**
```env
OPENAI_API_KEY=<ваш_ключ>
CLAUDE_API_KEY=<ваш_ключ>
TRANSLATION_API_KEY=<ваш_ключ>
CLAUDE_API_URL=https://api.anthropic.com/v1/messages
TRANSLATION_API_URL=https://mangisoz.nu.edu.kz/external-api/v1/translate/text/
```

**AWS S3:**
```env
AWS_ACCESS_KEY_ID=<ваш_ключ>
AWS_SECRET_ACCESS_KEY=<ваш_секрет>
AWS_REGION=us-east-1
S3_BUCKET_NAME=<имя_бакета>
```

**После деплоя frontend:**
```env
FRONTEND_URL=https://your-frontend.onrender.com
```

### 5. Проверка
```bash
curl https://your-backend.onrender.com/
# Должен вернуть: {"message": "DOCX Viewer API is running"}
```

### Документация API
- Swagger: `https://your-backend.onrender.com/docs`
- ReDoc: `https://your-backend.onrender.com/redoc`

---

Подробная документация: **RENDER_DEPLOY.md**
