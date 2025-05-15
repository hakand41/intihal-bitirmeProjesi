from flask import Flask, request, jsonify, render_template, abort
from config import UPLOAD_FOLDER
from upload import process_and_save_file
from compare import perform_comparison, get_content_info
from helpers import _strip_cleaned_suffix
from helpers import highlight_char_spans, read_text, highlight_texts, highlight_with_difflib, get_difflib_spans
from db_utils import get_db_connection
from flask_cors import CORS
import os
import time
import datetime
import subprocess
import threading
import webbrowser

app = Flask(__name__, template_folder='templates')
CORS(app, origins=["http://localhost:5173"])
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

VIEW_PROCS: dict[str, subprocess.Popen] = {}

CODE_LANGS = {
    "java","c","cpp","csharp","python3","javascript","typescript",
    "golang","kotlin","rlang","rust","swift","scala","llvmir","scheme",
    "emf","emf-model","scxml"
}

@ app.route('/upload', methods=['POST'])
def upload_file():
    try:
        user_id      = request.form.get('user_id')
        content_id   = request.form.get('content_id')
        baslik       = request.form.get('baslik')
        ad_soyad     = request.form.get('ad_soyad')
        icerik_turu  = request.form.get('icerik_turu')
        uploaded_file= request.files.get('file')

        if not all([user_id, content_id, baslik, ad_soyad, icerik_turu, uploaded_file]):
            return jsonify({"error": "Tüm alanlar gereklidir."}), 400

        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], baslik, ad_soyad)
        os.makedirs(user_folder, exist_ok=True)

        original_path = os.path.join(user_folder, uploaded_file.filename)
        uploaded_file.save(original_path)

        cleaned_path = process_and_save_file(original_path, user_id, content_id, icerik_turu)

        return jsonify({
            "message": "Dosya yüklendi ve işlendi.",
            "original_path": original_path,
            "cleaned_path": cleaned_path
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/compare', methods=['POST'])
def compare_files():
    try:
        if not request.is_json:
            return jsonify({"error": "İstek JSON olmalı."}), 415

        content_id = request.json.get('content_id')
        if not content_id:
            return jsonify({"error": "İçerik ID eksik."}), 400

        result = perform_comparison(content_id)

        if isinstance(result, float):
            return jsonify({
                "message": "Metin karşılaştırması tamamlandı.",
                "average_similarity": round(result, 4)
            }), 200

        elif isinstance(result, dict):
            return jsonify({
                "message": result.get("message", "Kod karşılaştırması tamamlandı."),
                "port": result.get("port"),
                "job_id": result.get("job_id"),
                "web_url": f"http://localhost:{result['port']}" if result.get("port") else None
            }), 200

        else:
            return jsonify({"error": "Bilinmeyen sonuç türü."}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/compare_html', methods=['POST'])
def compare_html():
    data = request.get_json(force=True)

    # Gerekli tüm anahtarlar
    required = ('KullaniciAdi1', 'KullaniciAdi2', 'Dosya1', 'Dosya2', 'BenzerlikOrani')
    for key in required:
        if key not in data:
            abort(400, f"'{key}' eksik.")

    # DÜZELTME: 'Kullanici2' yerine 'KullaniciAdi2'
    u1 = data['KullaniciAdi1']
    u2 = data['KullaniciAdi2']
    p1 = data['Dosya1']
    p2 = data['Dosya2']
    sim = data['BenzerlikOrani']

    # Dosya var mı kontrolü
    if not os.path.isfile(p1) or not os.path.isfile(p2):
        missing = p1 if not os.path.isfile(p1) else p2
        abort(404, f"Dosya bulunamadı: {missing}")

    # Temizlenmiş .txt/.docx/.pdf metinlerini oku
    raw1 = read_text(p1)
    raw2 = read_text(p2)

    # difflib tabanlı hızlı vurgulama
    h1, h2 = highlight_with_difflib(raw1, raw2, min_len=30)

    # HTML’de satır sonu için <br>
    h1 = h1.replace('\n', '<br>')
    h2 = h2.replace('\n', '<br>')

    return render_template(
        'compare.html',
        user1=u1,
        user2=u2,
        similarity=sim,
        text1=h1,
        text2=h2
    )

@app.route('/jplag/view', methods=['POST'])
def jplag_view():
    if not request.is_json:
        return jsonify({"error": "JSON bekleniyor."}), 415
    data = request.get_json()
    cid = data.get("content_id")
    if not cid:
        return jsonify({"error": "content_id eksik."}), 400

    # İçerikTuru çek
    try:
        lang, baslik = get_content_info(cid)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    if lang not in CODE_LANGS:
        return jsonify({"error": "Kod tabanlı değildir."}), 400

    # Önceki process var mı, hâlâ çalışıyor mu?
    prev = VIEW_PROCS.get(cid)
    already_running = False
    if prev and prev.poll() is None:
        # Hâlâ canlı, önce kapatmaya çalış
        try:
            prev.stdin.write("\n")
            prev.stdin.flush()
            prev.wait(timeout=5)
        except Exception:
            prev.kill()
        already_running = True

    # En son ZipPath’i al
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT TOP 1 ZipPath FROM JplagJobs WHERE IcerikId = ? ORDER BY CreatedAt DESC",
        (cid,)
    )
    row = cur.fetchone(); conn.close()
    if not row:
        return jsonify({"error": "Job bulunamadı."}), 404

    zip_path = os.path.abspath(row[0])
    if not os.path.isfile(zip_path):
        return jsonify({"error": f"Rapor zip bulunamadı: {zip_path}"}), 500

    # Yeni process’i stdin PIPE’li başlat
    port = 2999
    jar  = os.path.abspath("./jplag-6.0.0-jar-with-dependencies.jar")
    cmd  = ["java", "-jar", jar, zip_path, "-M", "VIEW", "-l", lang, "-P", str(port)]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        text=True
    )

    # Log akışını başlat
    def _stream():
        for ln in proc.stdout:
            print(f"[JPLAG] {ln.strip()}")
    threading.Thread(target=_stream, daemon=True).start()

    # Yeni process’i kaydet
    VIEW_PROCS[cid] = proc

    # **Sadece** eğer önceki süreç zaten açıksa veya ilk defa açıyorsak tarayıcıyı aç
    if not already_running:
        webbrowser.open(f"http://localhost:{port}")

    return jsonify({
        "message": "JPlag arayüzü başlatıldı.",
        "url": f"http://localhost:{port}"
    }), 200

@app.route('/compare_json', methods=['POST'])
def compare_json():
    data = request.get_json(force=True)

    required = ('KullaniciAdi1', 'KullaniciAdi2', 'Dosya1', 'Dosya2', 'BenzerlikOrani')
    for key in required:
        if key not in data:
            abort(400, f"'{key}' eksik.")

    u1 = data['KullaniciAdi1']
    u2 = data['KullaniciAdi2']
    p1 = data['Dosya1']
    p2 = data['Dosya2']

    try:
        sim = float(data['BenzerlikOrani'])
    except (TypeError, ValueError):
        abort(400, "'BenzerlikOrani' sayısal bir değer olmalı.")

    if not os.path.isfile(p1) or not os.path.isfile(p2):
        missing = p1 if not os.path.isfile(p1) else p2
        abort(404, f"Dosya bulunamadı: {missing}")

    start_time = time.time()

    raw1 = read_text(p1)
    raw2 = read_text(p2)

    spans1, spans2 = get_difflib_spans(raw1, raw2, min_len=25)

    words1 = raw1.split()
    words2 = raw2.split()
    set1, set2 = set(words1), set(words2)

    # ✅ Eşleşen kelimeleri logla
    matching_words = set1 & set2
    print(f"[LOG] Eşleşen kelimeler ({len(matching_words)}): {matching_words}")

    # ✅ Eşleşen blokları logla
    print(f"[LOG] Eşleşen bloklar spans1: {spans1}")
    print(f"[LOG] Eşleşen bloklar spans2: {spans2}")

    result = {
        "text1": raw1.replace('\n', '<br>'),
        "text2": raw2.replace('\n', '<br>'),
        "user1": u1,
        "user2": u2,
        "similarity": sim,
        "matchingWords": sorted(list(set1 & set2)),
        "totalWords1": len(words1),
        "totalWords2": len(words2),
        "matchingWordCount": len(matching_words),
        "uniqueWords1": len(set1 - set2),
        "uniqueWords2": len(set2 - set1),
        "matchSpans": [ 
            {"start1": s1, "length": l1, "start2": s2, "length": l2}
            for (s1, l1), (s2, l2) in zip(spans1, spans2)
        ],
        "diffSpans": [],
        "timeElapsed": round(time.time() - start_time, 4),
        "timestamp": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    }

    return jsonify(result), 200


if __name__ == '__main__':
    app.run(debug=True)
