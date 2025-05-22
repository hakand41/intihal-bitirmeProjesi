import os

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")


# config.py
DB_CONFIG = {
    'server':   '188.132.198.102',       # sadece IP (veya DNS adı)
    'port':     '1433',                  # SQL Server TCP port
    'database': 'OrjinalIntihalDb',
    'username': 'sa',
    'password': 'EFsAjwqBe8',
    'driver':   '{ODBC Driver 17 for SQL Server}'
}

UPLOAD_FOLDER = r'C:\Users\hakan\OneDrive\Masaüstü\deneme\uploads'

JSON_RESULTS_FOLDER  = os.path.join(UPLOAD_FOLDER, "json_results")
os.makedirs(JSON_RESULTS_FOLDER, exist_ok=True)