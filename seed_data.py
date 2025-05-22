import pyodbc
from datetime import datetime
from config import DB_CONFIG

conn_str = (
    f"DRIVER={DB_CONFIG['driver']};"
    f"SERVER={DB_CONFIG['server']},{DB_CONFIG['port']};"
    f"DATABASE={DB_CONFIG['database']};"
    f"UID={DB_CONFIG['username']};"
    f"PWD={DB_CONFIG['password']}"
)
conn = pyodbc.connect(conn_str, timeout=5)
cursor = conn.cursor()

users = [
    ('Test','Teacher','teacher@test.com','1','teacher'),
    ('Test','Student1','student1@test.com','1','student'),
    ('Test','Student2','student2@test.com','1','student'),
]

user_ids = []
for ad, soyad, email, sifre, rol in users:
    sql = """
    SET NOCOUNT ON;
    INSERT INTO dbo.Kullanicilar (Ad, Soyad, Eposta, Sifre, Rol)
    VALUES (?, ?, ?, ?, ?);
    SELECT SCOPE_IDENTITY();
    """
    cursor.execute(sql, ad, soyad, email, sifre, rol)
    new_id = cursor.fetchval()      # Şimdi doğru şekilde SCOPE_IDENTITY() dönecek
    user_ids.append(int(new_id))

print("Oluşturulan Kullanıcı ID’leri:", user_ids)

# İçerik ekleme
teacher_id  = user_ids[0]
sql2 = """
SET NOCOUNT ON;
INSERT INTO dbo.Icerikler
  (Baslik, Aciklama, OlusturmaTarihi, BitisTarihi, KullaniciId, IcerikTuru)
VALUES (?, ?, ?, ?, ?, ?);
"""
cursor.execute(sql2,
    'Test İçerik Başlığı',
    'Bu içerik yalnızca test amaçlıdır.',
    datetime.now(),
    None,
    teacher_id,
    'text'
)

conn.commit()
print("Test verileri başarıyla eklendi.")
cursor.close()
conn.close()
