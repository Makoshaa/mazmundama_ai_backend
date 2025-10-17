from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import mammoth
import io
from typing import List
from bs4 import BeautifulSoup
import re
import httpx
import os
from dotenv import load_dotenv
from openai import OpenAI

# Импорт роутеров для авторизации и работы с книгами
from auth_routes import router as auth_router
from books_routes import router as books_router

load_dotenv()

app = FastAPI(title="DOCX Viewer API (Mazmundama)")

# Подключаем роутеры
app.include_router(auth_router)
app.include_router(books_router)

# CORS Configuration
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174"
]

# Add production frontend URL if available
frontend_url = os.getenv('FRONTEND_URL')
if frontend_url:
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def wrap_sentences_in_html(html: str, sentence_counter: list = None) -> str:
    """Оборачивает предложения в span теги для подсветки с уникальными ID"""
    if sentence_counter is None:
        sentence_counter = [0]

    soup = BeautifulSoup(html, 'html.parser')

    def process_text_node(text):
        if not text.strip():
            return text

        sentences = re.split(r'([.!?]+[\s\n]+|[.!?]+$)', text)
        sentences = [s for s in sentences if s]

        result = []
        temp_sentence = ''

        for part in sentences:
            temp_sentence += part
            if re.search(r'[.!?]+[\s\n]*$', part):
                sentence_counter[0] += 1
                result.append(f'<span class="sentence" data-sentence-id="sent-{sentence_counter[0]}">{temp_sentence}</span>')
                temp_sentence = ''

        if temp_sentence.strip():
            sentence_counter[0] += 1
            result.append(f'<span class="sentence" data-sentence-id="sent-{sentence_counter[0]}">{temp_sentence}</span>')

        return ''.join(result)
    
    def process_element(element):
        if element.name is None:
            return process_text_node(str(element))
        
        for child in list(element.children):
            if child.name is None:
                new_html = process_text_node(str(child))
                from bs4 import BeautifulSoup as BS
                new_soup = BS(new_html, 'html.parser')
                child.replace_with(new_soup)
            else:
                process_element(child)
    
    process_element(soup)
    return str(soup)

def paginate_html(html: str, chars_per_page: int = 1800) -> List[str]:
    """Разбивает HTML на страницы"""
    soup = BeautifulSoup(html, 'html.parser')
    
    if soup.body:
        elements = list(soup.body.children)
    else:
        elements = list(soup.children)
    
    pages = []
    current_page = ''
    current_chars = 0
    
    for element in elements:
        if element.name is None:
            continue
            
        element_html = str(element)
        element_text = element.get_text()
        element_length = len(element_text)
        
        if current_chars > 0 and current_chars + element_length > chars_per_page:
            pages.append(current_page)
            current_page = element_html
            current_chars = element_length
        else:
            current_page += element_html
            current_chars += element_length
    
    if current_page:
        pages.append(current_page)
    
    return pages if pages else [html]

class TranslateRequest(BaseModel):
    text: str
    source_language: str = "eng"
    target_language: str = "kaz"
    model: str = "kazllm"  # "kazllm", "claude" или "chatgpt"

class ChatGPTRequest(BaseModel):
    message: str
    system_prompt: str = "You are a helpful assistant."
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 1000

class ClaudeRequest(BaseModel):
    message: str
    system_prompt: str = "You are a helpful assistant."
    model: str = "claude-sonnet-4-5-20250929"
    temperature: float = 0.7
    max_tokens: int = 4096

@app.get("/")
async def root():
    return {"message": "DOCX Viewer API is running"}

@app.post("/api/upload")
async def upload_docx(file: UploadFile = File(...)):
    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="Only DOCX files are allowed")
    
    try:
        contents = await file.read()
        
        style_map = """
        p[style-name='Heading 1'] => h1.heading-1:fresh
        p[style-name='Heading 2'] => h2.heading-2:fresh
        p[style-name='Heading 3'] => h3.heading-3:fresh
        p[style-name='Title'] => h1.title:fresh
        p[style-name='Subtitle'] => h2.subtitle:fresh
        r[style-name='Strong'] => strong
        p[style-name='Quote'] => blockquote:fresh
        p[style-name='Normal'] => p.normal:fresh
        p[style-name='Body Text'] => p.body-text:fresh
        p[style-name='List Paragraph'] => p.list-paragraph:fresh
        """
        
        result = mammoth.convert_to_html(
            io.BytesIO(contents),
            style_map=style_map,
            include_default_style_map=True,
            include_embedded_style_map=True
        )
        
        html_content = result.value
        
        soup = BeautifulSoup(html_content, 'html.parser')
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            if not p.get_text(strip=True) and not p.find('img'):
                p.string = '\u00a0'
        
        html_content = str(soup)
        
        html_with_spans = wrap_sentences_in_html(html_content)
        
        pages = paginate_html(html_with_spans)
        
        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "pages": pages,
            "total_pages": len(pages)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/api/translate")
async def translate_text(request: TranslateRequest):
    """Прокси endpoint для перевода текста через внешний API"""

    try:
        if request.model == "chatgpt":
            # Используем ChatGPT API для перевода
            OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
            
            if not OPENAI_API_KEY:
                raise HTTPException(status_code=500, detail="OpenAI API key not configured")
            
            try:
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)
                
                # Определяем языки
                lang_map = {
                    "eng": "English",
                    "kaz": "Kazakh",
                    "rus": "Russian"
                }
                
                source_lang = lang_map.get(request.source_language, request.source_language)
                target_lang = lang_map.get(request.target_language, request.target_language)
                
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a professional translator. Translate the given text accurately, preserving its meaning and tone. Only provide the translation without any explanations or additional text."},
                        {"role": "user", "content": f"Translate the following text from {source_lang} to {target_lang}:\n\n{request.text}"}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )
                
                translated_text = response.choices[0].message.content.strip()
                
                return JSONResponse({
                    "success": True,
                    "text": translated_text,
                    "source_language": request.source_language,
                    "target_language": request.target_language,
                    "model": "chatgpt"
                })
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"ChatGPT translation error: {str(e)}")
                
        elif request.model == "claude":
            # Используем Claude API
            CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
            CLAUDE_API_URL = os.getenv('CLAUDE_API_URL', 'https://api.anthropic.com/v1/messages')
            
            if not CLAUDE_API_KEY:
                raise HTTPException(status_code=500, detail="Claude API key not configured")

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    CLAUDE_API_URL,
                    headers={
                        'x-api-key': CLAUDE_API_KEY,
                        'anthropic-version': '2023-06-01',
                        'Content-Type': 'application/json',
                    },
                    json={
                        'model': 'claude-sonnet-4-5-20250929',
                        'max_tokens': 4096,
                        'messages': [{
                            'role': 'user',
                            'content': f'Translate the following text from English to Kazakh. Only provide the translation, no explanations:\n\n{request.text}'
                        }]
                    }
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Claude API error: {response.text}"
                    )

                data = response.json()
                translated_text = data['content'][0]['text'].strip()

                return JSONResponse({
                    "success": True,
                    "text": translated_text,
                    "source_language": request.source_language,
                    "target_language": request.target_language,
                    "model": "claude"
                })
        else:
            # Используем KazLLM API
            TRANSLATION_API_URL = os.getenv('TRANSLATION_API_URL', 'https://mangisoz.nu.edu.kz/external-api/v1/translate/text/')
            TRANSLATION_API_KEY = os.getenv('TRANSLATION_API_KEY')
            
            if not TRANSLATION_API_KEY:
                raise HTTPException(status_code=500, detail="Translation API key not configured")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    TRANSLATION_API_URL,
                    headers={
                        'Authorization': f'Bearer {TRANSLATION_API_KEY}',
                        'Content-Type': 'application/json',
                    },
                    json={
                        'source_language': request.source_language,
                        'target_language': request.target_language,
                        'text': request.text,
                    }
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Translation API error: {response.text}"
                    )

                data = response.json()
                return JSONResponse({
                    "success": True,
                    "text": data.get('text', request.text),
                    "source_language": request.source_language,
                    "target_language": request.target_language,
                    "model": "kazllm"
                })

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Translation service timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Translation service error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error translating text: {str(e)}")

@app.post("/api/chatgpt")
async def chat_with_gpt(request: ChatGPTRequest):
    """Endpoint для общения с ChatGPT API"""
    
    try:
        OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.message}
            ],
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        assistant_message = response.choices[0].message.content
        
        return JSONResponse({
            "success": True,
            "message": assistant_message,
            "model": request.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with ChatGPT: {str(e)}")

@app.post("/api/claude")
async def chat_with_claude(request: ClaudeRequest):
    """Endpoint для общения с Claude API"""
    
    try:
        CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
        CLAUDE_API_URL = os.getenv('CLAUDE_API_URL', 'https://api.anthropic.com/v1/messages')
        
        if not CLAUDE_API_KEY:
            raise HTTPException(status_code=500, detail="Claude API key not configured")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                CLAUDE_API_URL,
                headers={
                    'x-api-key': CLAUDE_API_KEY,
                    'anthropic-version': '2023-06-01',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': request.model,
                    'max_tokens': request.max_tokens,
                    'temperature': request.temperature,
                    'system': request.system_prompt,
                    'messages': [{
                        'role': 'user',
                        'content': request.message
                    }]
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Claude API error: {response.text}"
                )
            
            data = response.json()
            assistant_message = data['content'][0]['text']
            
            return JSONResponse({
                "success": True,
                "message": assistant_message,
                "model": request.model,
                "usage": {
                    "input_tokens": data['usage']['input_tokens'],
                    "output_tokens": data['usage']['output_tokens']
                }
            })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with Claude: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
