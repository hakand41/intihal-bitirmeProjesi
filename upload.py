# upload.py

import os
import re
from PyPDF2 import PdfReader
from docx import Document
from db_utils import get_db_connection
from config import UPLOAD_FOLDER
import nltk
nltk.download('stopwords')
from nltk.corpus import stopwords

# Türkçe stop-words
turkish_stop_words = set(stopwords.words('turkish'))

def extract_text_from_file(file_path):
    _, ext = os.path.splitext(file_path)
    if ext.lower() == '.pdf':
        return ''.join([page.extract_text() for page in PdfReader(file_path).pages])
    elif ext.lower() == '.docx' or '.doc':
        return ' '.join(p.text for p in Document(file_path).paragraphs)
    else:
        raise ValueError("Sadece PDF ve DOC(X) desteklenmektedir.")

def remove_document_metadata(text):
    patterns = [
        r'(?im)^başlık:.*$', 
        r'(?im)^içindekiler\b.*$', 
        r'(?im)^önsöz\b.*$', 
        r'(?im)^kaynakça\b.*$', 
        r'(?im)^sayfa\s*\d+\b'
    ]
    for p in patterns:
        text = re.sub(p, '', text)
    return text

def clean_text(text):
    # 1. Meta kısımları sil
    text = remove_document_metadata(text)
    # 2. Regex ile kelime bazlı tokenizasyon
    tokens = re.findall(r'\b\w+\b', text.lower(), flags=re.UNICODE)
    # 3. Stop-word temizle
    tokens = [t for t in tokens if t not in turkish_stop_words]
    return ' '.join(tokens)

def process_and_save_file(file_path, user_id, content_id, icerik_turu):
    try:
        
        if icerik_turu in ['kisa', 'orta', 'uzun', 'text', "doc", 'docx', 'pdf']:
            raw_text = extract_text_from_file(file_path)
            cleaned_text = clean_text(raw_text)
            cleaned_path = f"{file_path}_cleaned.txt"
            with open(cleaned_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_text)
        else:
            cleaned_path = file_path

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Dosyalar (CleanedPath, KullaniciId, IcerikId) VALUES (?, ?, ?)",
            (cleaned_path, user_id, content_id)
        )
        conn.commit()
        conn.close()

        return cleaned_path

    except Exception as e:
        raise RuntimeError(f"Dosya işleme hatası: {e}")
