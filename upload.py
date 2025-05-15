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
    """
    Verilen dosya yolundan metni çıkarır.
    - PDF için tüm sayfaları birleştirir
    - DOC/DOCX için paragrafları çift yeni satırla ayırarak korur
    - Diğer dosyalar (kod, txt vb.) için ham içeriği okur
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == '.pdf':
        # PDF içeriğini doğrudan birleştir
        return ''.join([page.extract_text() or '' for page in PdfReader(file_path).pages])

    elif ext in ('.docx', '.doc'):
        # Paragrafları çift yeni satır ile ayırarak koru
        return '\n\n'.join(p.text for p in Document(file_path).paragraphs)

    else:
        # Kod veya düz metin dosyası: ham içeriği oku
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()


def remove_document_metadata(text):
    """
    Metin içindeki başlık, içindekiler, önsöz, kaynakça ve sayfa numarası gibi
    belgedeki meta bölümleri temizler.
    """
    patterns = [
        r'(?im)^başlık:.*$',
        r'(?im)^içindekiler\b.*$',
        r'(?im)^önsöz\b.*$',
        r'(?im)^kaynakça\b.*$',
        r'(?im)^sayfa\s*\d+\b'
    ]
    for pat in patterns:
        text = re.sub(pat, '', text)
    return text


def clean_text(text):
    """
    Metni paragraf-paragraf temizler:
      1) Başlık/paragraf yapısını korur (tamamen büyük harfli satırları olduğu gibi bırakır)
      2) Metadata temizleme (remove_document_metadata)
      3) Tokenizasyon, stop-word ve sayı filtresi (tek harfli tokenlar çıkarılır)
      4) Sonuçları çift yeni satırla birleştirir
    """
    cleaned_paragraphs = []
    for para in text.split('\n\n'):
        stripped = para.strip()
        if not stripped:
            continue
        # Tamamen büyük harfli paragrafı (başlık) olduğu gibi koru
        if stripped.isupper():
            cleaned_paragraphs.append(stripped)
            continue

        # Metadata bölümlerini temizle
        t = remove_document_metadata(stripped)
        # Kelime bazlı tokenizasyon
        tokens = re.findall(r'\b\w+\b', t.lower(), flags=re.UNICODE)
        # Tek harfli tokenlar, stop-word ve sayısal içerikleri çıkar
        tokens = [
            w for w in tokens
            if len(w) > 1
               and w not in turkish_stop_words
               and not any(ch.isdigit() for ch in w)
        ]
        if tokens:
            cleaned_paragraphs.append(' '.join(tokens))

    # Paragrafları çift yeni satırla birleştir
    return '\n\n'.join(cleaned_paragraphs)


def process_and_save_file(file_path, user_id, content_id, icerik_turu):
    """
    Dosyayı işleyip temizlenmiş metni kaydeder ve veritabanına kaydeder.
    - PDF ve DOCX için clean_text uygulanır.
    - Diğer dosyalar (kod, txt vb.) orijinal haliyle saklanır.
    """
    try:
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext in ('.pdf', '.docx', '.doc'):
            raw_text = extract_text_from_file(file_path)
            cleaned_text = clean_text(raw_text)
            # Orijinal dosya adının sonuna '_cleaned.txt' ekle
            cleaned_path = f"{file_path}_cleaned.txt"
            with open(cleaned_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_text)
        else:
            # Kod/metin dosyaları için temizleme atla, orijinal dosya yolunu kullan
            cleaned_path = file_path

        # Veritabanına temizlenmiş dosya yolunu kaydet
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
