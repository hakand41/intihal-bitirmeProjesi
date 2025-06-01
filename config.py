import os

# Temel Celery Ayarları (Eski format)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Görevlerin bulunduğu modülleri belirtir.
# app.py içindeki @celery.task ile tanımlanan görevler için 'app' yeterlidir.
# Celery worker -A app.celery komutuyla başlatıldığında 'app' modülünü zaten hedefler.
CELERY_INCLUDE = ['app']

# Veritabanı Yapılandırması
DB_CONFIG = {
    'server': '', # SQL Server örneğiniz
    'database': '',                   # Veritabanı adınız
    'username': '',     # SQL Server kullanıcı adınız (LÜTFEN GERÇEK KULLANICI ADINIZLA DEĞİŞTİRİN)
    'password': '',           # SQL Server şifreniz (LÜTFEN GERÇEK ŞİFRENİZLE DEĞİŞTİRİN)
    'driver': '{ODBC Driver 17 for SQL Server}'
    # Eğer standart olmayan bir port kullanıyorsanız, buraya 'port': 1433 gibi ekleyebilirsiniz.
    # 'port': 1433 # Varsayılan port, gerekirse değiştirin
}

# Dosya Yükleme ve Sonuç Klasörleri
UPLOAD_FOLDER = r'' # Windows için raw string
JSON_RESULTS_FOLDER = os.path.join(UPLOAD_FOLDER, "json_results")

# Diğer Ayarlar
MIN_MATCH_LEN = 25

# JSON_RESULTS_FOLDER'ın var olduğundan emin ol
os.makedirs(JSON_RESULTS_FOLDER, exist_ok=True)
