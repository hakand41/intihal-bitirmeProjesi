import os
import uuid
import subprocess
import zipfile
import json
from config import UPLOAD_FOLDER
from db_utils import get_db_connection
from similarity_algorithms import (
    cosine_similarity_tfidf,
    jaccard_similarity,
    ngram_overlap,
    lsa_cosine_similarity,
    longest_common_subsequence,
    ast_similarity,
    levenshtein_similarity
)

# =====================
# Yardımcı fonksiyonlar
# =====================

def get_content_info(content_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT IcerikTuru, Baslik FROM Icerikler WHERE IcerikId = ?", (content_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ValueError(f"İçerik bulunamadı: {content_id}")
    return row[0], row[1]  # IcerikTuru, Baslik

def retrieve_user_to_dosya_id_map(content_id, baslik):
    base_path = os.path.join(UPLOAD_FOLDER, baslik)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DosyaId, CleanedPath FROM Dosyalar WHERE IcerikId = ?", (content_id,))
    rows = cursor.fetchall()
    conn.close()

    path_map = {}
    for dosya_id, path in rows:
        if not path: continue
        relative = os.path.relpath(path, base_path)
        parts = os.path.normpath(relative).split(os.sep)
        if len(parts) >= 2:
            user = parts[0]
            path_map[user] = dosya_id
    return path_map

def retrieve_content_from_db(content_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT CleanedPath, DosyaId FROM Dosyalar WHERE IcerikId = ?", (content_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"path": r[0], "id": r[1]} for r in rows]

def parse_jplag_results(zip_path, content_id):
    with zipfile.ZipFile(zip_path, 'r') as zf:
        overview = json.loads(zf.read("overview.json"))
        participants = overview["submission_id_to_display_name"].keys()

        icerik_turu, baslik = get_content_info(content_id)
        name_map = retrieve_user_to_dosya_id_map(content_id, baslik)

        conn = get_db_connection()
        cursor = conn.cursor()
        inserted = 0

        for entry in zf.namelist():
            if not entry.startswith("Student") or not entry.endswith(".json"):
                continue
            data = json.loads(zf.read(entry))
            n1, n2 = data["id1"], data["id2"]
            sim = data.get("first_similarity", data["similarities"].get("AVG"))
            id1, id2 = name_map.get(n1), name_map.get(n2)
            if id1 and id2:
                cursor.execute(
                    "INSERT INTO BenzerlikSonuclari (IlkDosyaId, IkinciDosyaId, IcerikId, BenzerlikOrani) VALUES (?, ?, ?, ?)",
                    (id1, id2, content_id, sim)
                )
                inserted += 1

        conn.commit()
        conn.close()
        return inserted

# =====================
# JPlag batch modu (UI açmadan ZIP üretir)
# =====================

def run_jplag_batch(source_folder, language):
    os.makedirs("results", exist_ok=True)
    job_id = str(uuid.uuid4())
    result_path = os.path.join("results", job_id)
    cmd = [
        "java", "-jar", "./jplag-6.0.0-jar-with-dependencies.jar",
        source_folder,
        "-l", language,
        "-M", "RUN",
        "-r", result_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return job_id, result_path + ".zip"

# =====================
# Metin benzerlik konfigürasyonu
# =====================

similarity_config = {
    "kisa":  {"algorithms": ["cosine","jaccard"],          "weights": [0.7,0.3]},
    "text":  {"algorithms": ["cosine","jaccard"],          "weights": [0.7,0.3]},
    "pdf":   {"algorithms": ["cosine","jaccard"],          "weights": [0.7,0.3]},
    "doc":   {"algorithms": ["cosine","jaccard"],          "weights": [0.7,0.3]},
    "docx":  {"algorithms": ["cosine","jaccard"],          "weights": [0.7,0.3]},
    "orta":  {"algorithms": ["cosine","jaccard","ngram"],  "weights": [0.5,0.2,0.3]},
    "uzun":  {"algorithms": ["lsa_cosine","lcs"],           "weights": [0.6,0.4]}
}

algorithm_functions = {
    "cosine":      cosine_similarity_tfidf,
    "jaccard":     jaccard_similarity,
    "ngram":       ngram_overlap,
    "lsa_cosine":  lsa_cosine_similarity,
    "lcs":         longest_common_subsequence,
    "ast":         ast_similarity,
    "levenshtein": levenshtein_similarity
}

# =====================
# Metin karşılaştırma
# =====================

def perform_text_comparison(content_id, icerik_turu):
    files = retrieve_content_from_db(content_id)
    if len(files) < 2:
        raise ValueError("Karşılaştırma için yeterli dosya yok.")

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    docs, ids = [], []
    for f in files:
        with open(f["path"], "r", encoding="utf-8", errors="ignore") as fp:
            docs.append(fp.read()); ids.append(f["id"])

    vec = TfidfVectorizer(ngram_range=(1,3))
    tfidf = vec.fit_transform(docs)
    cos_sim = cosine_similarity(tfidf)

    algs = similarity_config[icerik_turu]["algorithms"]
    wts  = similarity_config[icerik_turu]["weights"]

    conn = get_db_connection()
    cur = conn.cursor()
    for i in range(len(docs)):
        for j in range(i+1, len(docs)):
            base = cos_sim[i,j]
            combined = 0
            for alg, wt in zip(algs, wts):
                score = base if alg=="cosine" else algorithm_functions[alg](docs[i], docs[j])
                combined += score * wt
            cur.execute(
                "INSERT INTO BenzerlikSonuclari (IlkDosyaId, IkinciDosyaId, IcerikId, BenzerlikOrani) VALUES (?,?,?,?)",
                (ids[i], ids[j], content_id, combined)
            )
    conn.commit()
    conn.close()
    return cos_sim.mean()

# =====================
# Ana karşılaştırma
# =====================

def perform_comparison(content_id):
    icerik_turu, baslik = get_content_info(content_id)

    # JPlag destekli kod dilleri
    code_langs = {
        "java","c","cpp","csharp","python3","javascript","typescript",
        "golang","kotlin","rlang","rust","swift","scala","llvmir","scheme",
        "emf","emf-model","scxml"
    }

    if icerik_turu in code_langs:
        folder = os.path.join(UPLOAD_FOLDER, baslik)
        if not os.path.isdir(folder):
            raise FileNotFoundError(f"{folder} bulunamadı.")

        job_id, zip_path = run_jplag_batch(folder, icerik_turu)

        # Job kaydı
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO JplagJobs (JobId, IcerikId, ZipPath) VALUES (?,?,?)",
            (job_id, content_id, zip_path)
        )
        conn.commit()
        conn.close()

        return {
            "message": "JPlag batch çalıştırıldı.",
            "job_id": job_id,
            "zip_path": zip_path
        }
    else:
        # Metin tabanlı karşılaştırma
        return perform_text_comparison(content_id, icerik_turu)
