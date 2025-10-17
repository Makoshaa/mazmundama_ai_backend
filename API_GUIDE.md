# API Integration Guide

## Обзор

Backend приложение на FastAPI с интеграцией трех AI сервисов:
- **ChatGPT (OpenAI)** - для общения с GPT моделями
- **Claude (Anthropic)** - для перевода через Claude API
- **KazLLM** - для перевода на казахский язык

## Безопасность API ключей

### Важно! 🔐

API ключи хранятся в файле `.env`, который **НЕ должен** быть добавлен в Git.

### Настройка окружения

1. Скопируйте `.env.example` в `.env`:
   ```bash
   copy .env.example .env
   ```

2. Заполните `.env` своими ключами:
   ```env
   OPENAI_API_KEY=ваш_openai_ключ
   CLAUDE_API_KEY=ваш_claude_ключ
   TRANSLATION_API_KEY=ваш_translation_ключ
   ```

3. Убедитесь, что `.env` в `.gitignore` (уже настроено)

## Установка зависимостей

```bash
cd backend
pip install -r requirements.txt
```

## Запуск сервера

```bash
python main.py
```

Сервер запустится на `http://127.0.0.1:8080`

## API Endpoints

### 1. ChatGPT API

**Endpoint:** `POST /api/chatgpt`

**Описание:** Общение с ChatGPT

**Request Body:**
```json
{
  "message": "Объясни что такое машинное обучение",
  "system_prompt": "Ты полезный ассистент",
  "model": "gpt-4",
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**Параметры:**
- `message` (обязательно) - сообщение для ChatGPT
- `system_prompt` (опционально) - системный промпт, по умолчанию "You are a helpful assistant."
- `model` (опционально) - модель GPT, по умолчанию "gpt-4"
  - Доступны: "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"
- `temperature` (опционально) - креативность ответа (0.0-2.0), по умолчанию 0.7
- `max_tokens` (опционально) - максимум токенов в ответе, по умолчанию 1000

**Response:**
```json
{
  "success": true,
  "message": "Машинное обучение - это...",
  "model": "gpt-4",
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 150,
    "total_tokens": 175
  }
}
```

**Пример использования (JavaScript):**
```javascript
const response = await fetch('http://127.0.0.1:8080/api/chatgpt', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: 'Привет! Как дела?',
    model: 'gpt-4',
    temperature: 0.7
  })
});

const data = await response.json();
console.log(data.message);
```

**Пример использования (Python):**
```python
import requests

response = requests.post('http://127.0.0.1:8080/api/chatgpt', json={
    'message': 'Привет! Как дела?',
    'model': 'gpt-4',
    'temperature': 0.7
})

data = response.json()
print(data['message'])
```

### 2. Claude API

**Endpoint:** `POST /api/claude`

**Описание:** Общение с Claude 4.5 Sonnet

**Request Body:**
```json
{
  "message": "Объясни что такое нейронные сети",
  "system_prompt": "Ты полезный ассистент",
  "model": "claude-sonnet-4-5-20250929",
  "temperature": 0.7,
  "max_tokens": 4096
}
```

**Параметры:**
- `message` (обязательно) - сообщение для Claude
- `system_prompt` (опционально) - системный промпт, по умолчанию "You are a helpful assistant."
- `model` (опционально) - модель Claude, по умолчанию "claude-sonnet-4-5-20250929" (можно использовать алиас "claude-sonnet-4-5")
- `temperature` (опционально) - креативность ответа (0.0-1.0), по умолчанию 0.7
- `max_tokens` (опционально) - максимум токенов в ответе, по умолчанию 4096

**Response:**
```json
{
  "success": true,
  "message": "Нейронные сети - это...",
  "model": "claude-sonnet-4-5-20250929",
  "usage": {
    "input_tokens": 25,
    "output_tokens": 150
  }
}
```

**Пример использования (JavaScript):**
```javascript
const response = await fetch('http://127.0.0.1:8080/api/claude', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: 'Привет! Расскажи о машинном обучении',
    model: 'claude-sonnet-4-5-20250929',  // или используйте алиас 'claude-sonnet-4-5'
    temperature: 0.7
  })
});

const data = await response.json();
console.log(data.message);
```

### 3. Перевод текста

**Endpoint:** `POST /api/translate`

**Описание:** Перевод текста через ChatGPT, Claude или KazLLM

**Request Body:**
```json
{
  "text": "Hello world",
  "source_language": "eng",
  "target_language": "kaz",
  "model": "kazllm"
}
```

**Параметры:**
- `text` (обязательно) - текст для перевода
- `source_language` (опционально) - язык источника, по умолчанию "eng"
  - Поддерживаемые: "eng" (English), "kaz" (Kazakh), "rus" (Russian)
- `target_language` (опционально) - целевой язык, по умолчанию "kaz"
- `model` (опционально) - модель перевода: "kazllm", "claude" или "chatgpt", по умолчанию "kazllm"
  - **chatgpt** - OpenAI GPT-4 (высокое качество, универсальная поддержка языков)
  - **claude** - Anthropic Claude 4.5 Sonnet (высочайшее качество)
  - **kazllm** - специализированная модель для казахского языка

**Response:**
```json
{
  "success": true,
  "text": "Сәлем әлем",
  "source_language": "eng",
  "target_language": "kaz",
  "model": "kazllm"
}
```

### 4. Загрузка DOCX файла

**Endpoint:** `POST /api/upload`

**Описание:** Конвертация DOCX в HTML с разбиением на страницы

**Request:** Multipart form-data с файлом

**Response:**
```json
{
  "success": true,
  "filename": "document.docx",
  "pages": ["<html>...</html>", "..."],
  "total_pages": 5
}
```

## Обработка ошибок

Все endpoints возвращают HTTP статус коды:
- `200` - успех
- `400` - неверный запрос
- `500` - ошибка сервера
- `503` - сервис недоступен
- `504` - таймаут

Формат ошибки:
```json
{
  "detail": "Описание ошибки"
}
```

## Best Practices

1. **Никогда не коммитьте `.env`** - ваши API ключи останутся в истории Git!
2. **Используйте `.env.example`** - для документирования необходимых переменных
3. **Проверяйте ключи** - API вернет 500 ошибку если ключ не настроен
4. **Обрабатывайте ошибки** - всегда проверяйте `success` в ответе
5. **Ротация ключей** - меняйте ключи регулярно для безопасности

## Мониторинг использования

ChatGPT endpoint возвращает информацию об использовании токенов:
```json
{
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 150,
    "total_tokens": 175
  }
}
```

Используйте это для отслеживания затрат на API.

## Поддержка

При возникновении проблем проверьте:
1. Установлены ли все зависимости: `pip install -r requirements.txt`
2. Настроен ли `.env` файл с корректными ключами
3. Запущен ли сервер на порту 8080
4. Правильно ли настроены CORS origins для вашего frontend
