import os

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")


# config.py
DB_CONFIG = {
    'server': 'DESKTOP-GT2ME32\\MSSQLSERVER03',
    'database': 'deneme2',
    'username': 'yeni_kullanici_adiniz',
    'password': 'GucLuP@rol@2025',
    'driver': '{ODBC Driver 17 for SQL Server}'
}

UPLOAD_FOLDER = r'C:\Users\hakan\OneDrive\Masaüstü\deneme\uploads'

