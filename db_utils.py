# db_utils.py
import pyodbc
from config import DB_CONFIG # DB_CONFIG artık port bilgisi de içerebilir

def get_db_connection():
    # config.py'deki DB_CONFIG sözlüğünde 'port' anahtarının olup olmadığını kontrol et
    server_details = DB_CONFIG['server']
    if 'port' in DB_CONFIG and DB_CONFIG['port']: # Port belirtilmişse ve boş değilse
        server_details = f"{DB_CONFIG['server']},{DB_CONFIG['port']}"

    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={server_details};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']};"
        # Bağlantı hatalarını daha hızlı fark etmek için timeout eklenebilir
        # f"TIMEOUT=30;" # Saniye cinsinden
    )
    try:
        conn = pyodbc.connect(conn_str)
        return conn
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        # Hata loglama veya daha spesifik hata yönetimi eklenebilir
        print(f"Veritabanı bağlantı hatası: {sqlstate} - {ex}")
        raise # Hatayı yeniden fırlat, böylece çağıran kısım haberdar olur
