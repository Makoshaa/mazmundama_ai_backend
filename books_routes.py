"""
Роуты для работы с книгами и переводами
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from database import get_db_connection
from s3_storage import upload_file_to_s3, download_file_from_s3, delete_file_from_s3
from auth import get_current_user
import mammoth
import io
from bs4 import BeautifulSoup
import re

router = APIRouter(prefix="/api/books", tags=["Books"])

def wrap_sentences_in_html(html: str, sentence_counter: list = None) -> str:
    """Оборачивает абзацы в span теги для подсветки с уникальными ID"""
    if sentence_counter is None:
        sentence_counter = [0]

    soup = BeautifulSoup(html, 'html.parser')

    # Ищем все параграфы и заголовки
    for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']):
        # Пропускаем пустые элементы
        if not element.get_text(strip=True):
            continue
        
        sentence_counter[0] += 1
        
        # Извлекаем весь контент элемента (включая вложенные теги)
        content = ''.join(str(child) for child in element.children)
        
        # Очищаем элемент и добавляем span с контентом
        element.clear()
        from bs4 import BeautifulSoup as BS
        span = BS(f'<span class="sentence" data-sentence-id="sent-{sentence_counter[0]}">{content}</span>', 'html.parser')
        element.append(span)
    
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

class TranslationSaveRequest(BaseModel):
    book_id: int
    page_number: int
    sentence_id: str
    original_text: str
    translation: str
    model: Optional[str] = None

class ApproveTranslationRequest(BaseModel):
    book_id: int
    sentence_id: str

@router.post("/upload")
async def upload_book(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Загрузка книги в S3, обработка и сохранение в БД"""
    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="Только DOCX файлы поддерживаются")
    
    user_id = current_user["user_id"]
    
    # Читаем файл
    file_content = await file.read()
    
    # Создаем S3 ключ
    s3_key = f"users/{user_id}/books/{file.filename}"
    
    try:
        # Загружаем в S3
        upload_file_to_s3(
            file_content, 
            s3_key, 
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
        # Конвертируем DOCX в HTML и обрабатываем
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
            io.BytesIO(file_content),
            style_map=style_map,
            include_default_style_map=True,
            include_embedded_style_map=True
        )
        html_content = result.value
        
        # Удаляем все изображения из HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        for img in soup.find_all('img'):
            img.decompose()
        
        # Обрабатываем пустые параграфы
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            if not p.get_text(strip=True):
                p.string = '\u00a0'
        html_content = str(soup)
        
        # Оборачиваем предложения в span для подсветки
        html_with_spans = wrap_sentences_in_html(html_content)
        
        # Разбиваем на страницы
        pages = paginate_html(html_with_spans)
        
        # Подсчитываем общее количество предложений
        total_sentences = 0
        for page_html in pages:
            page_soup = BeautifulSoup(page_html, 'html.parser')
            sentences = page_soup.find_all('span', {'class': 'sentence'})
            total_sentences += len(sentences)
        
        # Сохраняем в БД
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Создаем/обновляем запись книги
            cursor.execute(
                """
                INSERT INTO books (user_id, title, s3_key, total_pages, total_sentences) 
                VALUES (%s, %s, %s, %s, %s) 
                ON CONFLICT (user_id, s3_key) 
                DO UPDATE SET title = EXCLUDED.title, 
                              total_pages = EXCLUDED.total_pages,
                              total_sentences = EXCLUDED.total_sentences
                RETURNING id
                """,
                (user_id, file.filename, s3_key, len(pages), total_sentences)
            )
            book_id = cursor.fetchone()['id']
            
            # Удаляем старые страницы если они были
            cursor.execute("DELETE FROM book_pages WHERE book_id = %s", (book_id,))
            
            # Сохраняем страницы
            for page_num, page_html in enumerate(pages, start=1):
                cursor.execute(
                    """
                    INSERT INTO book_pages (book_id, page_number, html_content)
                    VALUES (%s, %s, %s)
                    """,
                    (book_id, page_num, page_html)
                )
            
            conn.commit()
        
        return {
            "success": True,
            "book_id": book_id,
            "s3_key": s3_key,
            "pages": pages,
            "total_pages": len(pages),
            "total_sentences": total_sentences
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")

@router.get("/list")
async def list_books(current_user: dict = Depends(get_current_user)):
    """Список книг пользователя с статистикой переводов"""
    user_id = current_user["user_id"]
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                b.id, 
                b.title, 
                b.s3_key, 
                b.uploaded_at,
                b.total_pages,
                b.total_sentences,
                COUNT(DISTINCT t.sentence_id) as translated_sentences
            FROM books b
            LEFT JOIN translations t ON b.id = t.book_id
            WHERE b.user_id = %s 
            GROUP BY b.id, b.title, b.s3_key, b.uploaded_at, b.total_pages, b.total_sentences
            ORDER BY b.uploaded_at DESC
            """,
            (user_id,)
        )
        books = cursor.fetchall()
    
    return {"books": books}

@router.get("/{book_id}")
async def get_book(book_id: int, current_user: dict = Depends(get_current_user)):
    """Получить книгу и её переводы из БД"""
    user_id = current_user["user_id"]
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем книгу
        cursor.execute(
            "SELECT id, title, s3_key, total_pages, total_sentences FROM books WHERE id = %s AND user_id = %s",
            (book_id, user_id)
        )
        book = cursor.fetchone()
        
        if not book:
            raise HTTPException(status_code=404, detail="Книга не найдена")
        
        # Загружаем страницы из БД
        try:
            cursor.execute(
                """
                SELECT page_number, html_content 
                FROM book_pages 
                WHERE book_id = %s 
                ORDER BY page_number
                """,
                (book_id,)
            )
            pages_data = cursor.fetchall()
            
            if not pages_data:
                raise HTTPException(status_code=500, detail="Страницы книги не найдены в БД")
            
            pages = [page['html_content'] for page in pages_data]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")
        
        # Получаем переводы
        cursor.execute(
            """
            SELECT sentence_id, page_number, current_translation, is_approved 
            FROM translations 
            WHERE book_id = %s
            """,
            (book_id,)
        )
        translations = cursor.fetchall()
        
        # Получаем все версии переводов для всех предложений
        versions_by_sentence = {}
        try:
            cursor.execute(
                """
                SELECT t.sentence_id, tv.text, tv.model, tv.created_at
                FROM translation_versions tv
                JOIN translations t ON tv.translation_id = t.id
                WHERE t.book_id = %s
                ORDER BY t.sentence_id, tv.created_at ASC
                """,
                (book_id,)
            )
            versions = cursor.fetchall()
            
            # Группируем версии по sentence_id
            for version in versions:
                sentence_id = version['sentence_id']
                if sentence_id not in versions_by_sentence:
                    versions_by_sentence[sentence_id] = []
                versions_by_sentence[sentence_id].append({
                    'text': version['text'],
                    'model': version['model'],
                    'timestamp': int(version['created_at'].timestamp() * 1000)  # Конвертируем в миллисекунды
                })
            
            print(f"[DEBUG BACKEND] book_id={book_id}, translations={len(translations)}, versions_total={len(versions)}, versions_by_sentence={len(versions_by_sentence)}")
            if versions_by_sentence:
                first_key = list(versions_by_sentence.keys())[0]
                print(f"[DEBUG BACKEND] Sample: {first_key} has {len(versions_by_sentence[first_key])} versions")
        except Exception as e:
            print(f"[WARNING] Failed to load translation versions: {str(e)}")
            # Если таблица не существует или есть ошибка, продолжаем без версий
            versions_by_sentence = {}
    
    return {
        "book": book,
        "pages": pages,
        "total_pages": len(pages),
        "translations": {t['sentence_id']: t for t in translations},
        "versions": versions_by_sentence
    }

@router.post("/translation/save")
async def save_translation(
    request: TranslationSaveRequest,
    current_user: dict = Depends(get_current_user)
):
    """Сохранить перевод предложения"""
    user_id = current_user["user_id"]
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Проверяем что книга принадлежит пользователю
        cursor.execute(
            "SELECT id FROM books WHERE id = %s AND user_id = %s",
            (request.book_id, user_id)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Доступ запрещен")
        
        # Сохраняем или обновляем перевод
        cursor.execute(
            """
            INSERT INTO translations (book_id, page_number, sentence_id, original_text, current_translation)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (book_id, sentence_id) 
            DO UPDATE SET current_translation = EXCLUDED.current_translation, updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (request.book_id, request.page_number, request.sentence_id, request.original_text, request.translation)
        )
        translation_id = cursor.fetchone()['id']
        
        # Добавляем версию в историю
        cursor.execute(
            """
            INSERT INTO translation_versions (translation_id, text, model)
            VALUES (%s, %s, %s)
            """,
            (translation_id, request.translation, request.model)
        )
        
        conn.commit()
    
    return {"success": True, "translation_id": translation_id}

@router.get("/translation/{book_id}/history")
async def get_translation_history(
    book_id: int,
    sentence_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Получить историю версий перевода"""
    user_id = current_user["user_id"]
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Проверяем доступ
        cursor.execute(
            "SELECT id FROM books WHERE id = %s AND user_id = %s",
            (book_id, user_id)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Доступ запрещен")
        
        # Получаем историю
        cursor.execute(
            """
            SELECT tv.text, tv.model, tv.created_at
            FROM translation_versions tv
            JOIN translations t ON tv.translation_id = t.id
            WHERE t.book_id = %s AND t.sentence_id = %s
            ORDER BY tv.created_at ASC
            """,
            (book_id, sentence_id)
        )
        history = cursor.fetchall()
    
    return {"history": history}

@router.post("/translation/approve")
async def approve_translation(
    request: ApproveTranslationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Одобрить перевод"""
    user_id = current_user["user_id"]
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Проверяем доступ
        cursor.execute(
            "SELECT id FROM books WHERE id = %s AND user_id = %s",
            (request.book_id, user_id)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Доступ запрещен")
        
        # Обновляем статус
        cursor.execute(
            """
            UPDATE translations 
            SET is_approved = TRUE
            WHERE book_id = %s AND sentence_id = %s
            """,
            (request.book_id, request.sentence_id)
        )
        conn.commit()
    
    return {"success": True}

@router.delete("/{book_id}")
async def delete_book(book_id: int, current_user: dict = Depends(get_current_user)):
    """Удалить книгу"""
    user_id = current_user["user_id"]
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем книгу
        cursor.execute(
            "SELECT s3_key FROM books WHERE id = %s AND user_id = %s",
            (book_id, user_id)
        )
        book = cursor.fetchone()
        
        if not book:
            raise HTTPException(status_code=404, detail="Книга не найдена")
        
        # Удаляем из S3
        delete_file_from_s3(book['s3_key'])
        
        # Удаляем из БД (каскадное удаление переводов)
        cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))
        conn.commit()
    
    return {"success": True}
