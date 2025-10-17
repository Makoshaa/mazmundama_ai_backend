# Развертывание Backend на Render

Это руководство поможет развернуть backend приложение Mazmundama на платформе Render.

## Предварительные требования

1. Аккаунт на [Render.com](https://render.com)
2. GitHub репозиторий с кодом проекта
3. API ключи для сервисов (OpenAI, Claude, Translation API)
4. AWS S3 bucket для хранения файлов

## Шаг 1: Подготовка репозитория

Убедитесь, что все необходимые файлы добавлены в репозиторий:
- `requirements.txt` - зависимости Python (включая gunicorn)
- `build.sh` - скрипт сборки
- `start.sh` - скрипт запуска приложения
- `render.yaml` - конфигурация Render (опционально)

```bash
git add .
git commit -m "Prepare backend for Render deployment"
git push origin main
```

## Шаг 2: Создание PostgreSQL базы данных

1. Войдите в [Render Dashboard](https://dashboard.render.com)
2. Нажмите **"New +"** → **"PostgreSQL"**
3. Заполните форму:
   - **Name**: `mazmundama-db`
   - **Database**: `mazmundama`
   - **Region**: выберите ближайший регион
   - **Plan**: Free (для тестирования)
4. Нажмите **"Create Database"**
5. Сохраните **Internal Database URL** - он понадобится для настройки

## Шаг 3: Создание Web Service

### Способ 1: Через render.yaml (рекомендуется)

1. В Render Dashboard нажмите **"New +"** → **"Blueprint"**
2. Подключите GitHub репозиторий
3. Render автоматически обнаружит `render.yaml` и создаст сервисы
4. Настройте переменные окружения (см. Шаг 4)

### Способ 2: Вручную

1. В Render Dashboard нажмите **"New +"** → **"Web Service"**
2. Подключите GitHub репозиторий
3. Заполните форму:
   - **Name**: `mazmundama-backend`
   - **Region**: тот же, что и для базы данных
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `bash build.sh`
   - **Start Command**: `bash start.sh`
   - **Plan**: Free (для тестирования)

## Шаг 4: Настройка переменных окружения

Добавьте следующие переменные окружения в настройках Web Service:

### Обязательные переменные

```env
# Database (автоматически из PostgreSQL)
DATABASE_URL=<Internal_Database_URL_from_Step_2>

# JWT Authentication
JWT_SECRET_KEY=<generate_random_secure_string>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Keys
OPENAI_API_KEY=<your_openai_api_key>
CLAUDE_API_KEY=<your_claude_api_key>
TRANSLATION_API_KEY=<your_translation_api_key>

# API URLs
CLAUDE_API_URL=https://api.anthropic.com/v1/messages
TRANSLATION_API_URL=https://mangisoz.nu.edu.kz/external-api/v1/translate/text/

# AWS S3 Storage
AWS_ACCESS_KEY_ID=<your_aws_access_key>
AWS_SECRET_ACCESS_KEY=<your_aws_secret_access_key>
AWS_REGION=us-east-1
S3_BUCKET_NAME=<your_bucket_name>

# Frontend URL (добавьте после деплоя frontend)
FRONTEND_URL=https://your-frontend.onrender.com
```

### Генерация JWT_SECRET_KEY

Используйте команду для генерации безопасного ключа:

```python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Шаг 5: Настройка CORS

После деплоя frontend, обновите переменную `FRONTEND_URL` в настройках Web Service и перезапустите сервис.

## Шаг 6: Проверка деплоя

1. После успешного деплоя откройте URL вашего сервиса
2. Проверьте работу API:
   ```bash
   curl https://your-backend.onrender.com/
   ```
3. Должен вернуться ответ: `{"message": "DOCX Viewer API is running"}`
4. Проверьте документацию API:
   - Swagger UI: `https://your-backend.onrender.com/docs`
   - ReDoc: `https://your-backend.onrender.com/redoc`

## Шаг 7: Мониторинг и логи

- В Render Dashboard перейдите в созданный Web Service
- Вкладка **"Logs"** показывает логи приложения в реальном времени
- Вкладка **"Metrics"** показывает статистику использования ресурсов
- Вкладка **"Events"** показывает историю деплоев

## Автоматические деплои

Render автоматически переразвертывает приложение при:
- Push в ветку `main` (или выбранную ветку)
- Изменении переменных окружения

Для отключения автоматических деплоев:
1. Настройки Web Service → **"Auto-Deploy"** → выключите

## Troubleshooting

### Ошибка при инициализации БД

Если `init_db.py` падает с ошибкой:
1. Проверьте правильность `DATABASE_URL`
2. Убедитесь, что PostgreSQL база создана
3. Проверьте логи в Render Dashboard

### Ошибки CORS

Если frontend не может подключиться к backend:
1. Убедитесь, что `FRONTEND_URL` добавлен в переменные окружения
2. Перезапустите Web Service после изменения переменных
3. Проверьте настройки CORS в `main.py`

### Таймауты при запуске

Free plan на Render может "засыпать" после периода неактивности:
- Первый запрос после "пробуждения" может занять 30-60 секунд
- Для постоянной работы рассмотрите платный план

### Проблемы с зависимостями

Если build падает:
1. Проверьте `requirements.txt` на ошибки
2. Убедитесь, что все зависимости совместимы
3. Проверьте версию Python (по умолчанию 3.11)

## Бесплатные лимиты Render

- **PostgreSQL Free**: 1GB хранилище, 90 дней после последнего использования
- **Web Service Free**: 750 часов в месяц, "засыпает" после 15 минут неактивности
- **Bandwidth**: 100GB в месяц

## Обновление приложения

1. Внесите изменения в код локально
2. Закоммитьте и запушьте в GitHub:
   ```bash
   git add .
   git commit -m "Update backend"
   git push origin main
   ```
3. Render автоматически запустит новый деплой

## Полезные ссылки

- [Render Documentation](https://render.com/docs)
- [Render Status](https://status.render.com/)
- [Render Community](https://community.render.com/)

## Поддержка

При возникновении проблем:
1. Проверьте логи в Render Dashboard
2. Убедитесь, что все переменные окружения настроены
3. Проверьте статус Render: https://status.render.com/
