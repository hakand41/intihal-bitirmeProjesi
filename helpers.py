# helpers.py
import random, os, re, unicodedata
from docx import Document
from difflib import SequenceMatcher

try:
    import pdfplumber
    _PDF_BACKEND = 'pdfplumber'
except ImportError:
    from PyPDF2 import PdfReader
    _PDF_BACKEND = 'pypdf2'

def random_color():
    return "#{:06x}".format(random.randint(0x555555, 0xFFFFFF))

def remove_hyphens(text):
    return re.sub(r'-\s*\n\s*', '', text)

def normalize_text(text):
    txt = unicodedata.normalize('NFC', text).lower().replace('\n', ' ')
    return ''.join(c for c in txt if c.isalnum() or c.isspace() or c in 'çğıöşüâîû')

def read_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.docx':
        return '\n'.join(p.text for p in Document(path).paragraphs)
    elif ext == '.pdf':
        if _PDF_BACKEND == 'pdfplumber':
            pages = [remove_hyphens(p.extract_text() or '') for p in pdfplumber.open(path).pages]
            return '\n\n'.join(pages)
        else:
            reader = PdfReader(path)
            pages = [remove_hyphens(page.extract_text() or '') for page in reader.pages]
            return '\n\n'.join(pages)
    elif ext == '.txt':
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    # diğer uzantılar
    for enc in ('utf-8','latin-1'):
        try:
            return open(path, encoding=enc).read()
        except:
            continue
    return open(path, 'rb').read().decode('utf-8', errors='ignore')

def apply_char_highlighting(text, spans, colors):
    result = text
    for (start, length), color in sorted(zip(spans, colors), key=lambda x: x[0][0], reverse=True):
        seg = result[start:start+length]
        result = result[:start] + f'<span style="background-color:{color}">{seg}</span>' + result[start+length:]
    return result

def highlight_char_spans(t1, t2, min_len=20):
    n1, n2 = normalize_text(t1), normalize_text(t2)
    matches = []
    for L in range(min(len(n1),len(n2)), min_len-1, -1):
        for i in range(len(n1)-L+1):
            sub = n1[i:i+L]
            j = n2.find(sub)
            if j>=0 and not any(i<a2 and i+L>a1 for a1,a2,_,_ in matches):
                matches.append((i, i+L, j, j+L))
    def map_pos(norm, orig, p):
        cnt=0
        for idx,ch in enumerate(orig):
            if ch.isalnum() or ch.isspace() or ch in 'çğıöşüâîû':
                if cnt==p: return idx
                cnt+=1
        return len(orig)
    spans1, spans2 = [], []
    for i1,i2,j1,j2 in matches:
        o1,o2 = map_pos(n1,t1,i1), map_pos(n1,t1,i2)
        p1,p2 = map_pos(n2,t2,j1), map_pos(n2,t2,j2)
        spans1.append((o1,o2-o1)); spans2.append((p1,p2-p1))
    return spans1, spans2

def highlight_texts(t1, t2):
    spans1, spans2 = highlight_char_spans(t1, t2)
    if not spans1:
        return t1, t2
    colors = [random_color() for _ in spans1]
    return (
        apply_char_highlighting(t1, spans1, colors),
        apply_char_highlighting(t2, spans2, colors)
    )

def highlight_with_difflib(t1: str, t2: str, min_len: int = 100):
    """
    t1 ve t2 üzerinde SequenceMatcher kullanarak en az `min_len`
    uzunluğundaki eşleşen blokları boyar.
    """
    matcher = SequenceMatcher(None, t1, t2, autojunk=False)
    spans1, spans2, colors = [], [], []
    for block in matcher.get_matching_blocks():
        i, j, size = block.a, block.b, block.size
        if size >= min_len:
            spans1.append((i, size))
            spans2.append((j, size))
            colors.append(random_color())
    h1 = apply_char_highlighting(t1, spans1, colors)
    h2 = apply_char_highlighting(t2, spans2, colors)
    return h1, h2

def get_difflib_spans(t1: str, t2: str, min_len: int = 30):
    """
    SequenceMatcher.get_matching_blocks() ile hızlıca eşleşen blokları döner.
    """
    matcher = SequenceMatcher(None, t1, t2, autojunk=False)
    spans1, spans2 = [], []
    for block in matcher.get_matching_blocks():
        if block.size >= min_len:
            spans1.append((block.a, block.size))
            spans2.append((block.b, block.size))
    return spans1, spans2

def _strip_cleaned_suffix(path):
    """
    Eğer path "_cleaned.txt" veya "_cleaned.docx" ile bitiyorsa,
    orijinal dosya adına dönüştürür.
    """
    if path.endswith('_cleaned.txt'):
        # "tasarim_raporu.docx_cleaned.txt" -> "tasarim_raporu.docx"
        return path[:-len('_cleaned.txt')]
    if path.endswith('_cleaned.docx'):
        # "tasarim_raporu_cleaned.docx" -> "tasarim_raporu.docx"
        return path[:-len('_cleaned.docx')] + '.docx'
    return path