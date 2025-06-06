# async_tasks_utils.py
import os
import time
import datetime
from datetime import timezone
import uuid
import json
from flask import current_app # Flask uygulama bağlamına erişim için
from db_utils import get_db_connection # Veritabanı bağlantısı için
from helpers import read_text, get_difflib_spans # Metin okuma ve fark bulma için

# compare modülünden retrieve_content_from_db import edilmemiş,
# ancak get_all_file_pairs_for_content gibi bir fonksiyonunuz varsa
# ve bu fonksiyon dosyaların ID'lerini ve path'lerini veritabanından çekiyorsa,
# o fonksiyonun doğru çalıştığından emin olun.
# Eğer bu fonksiyonlar db_utils.py içerisindeyse oradan import edilmeli.

def get_user_info_for_file_task(dosya_id):
    """
    Verilen dosya ID'sine sahip kullanıcının adını ve soyadını döndürür.
    Bu fonksiyon Celery task içerisinde çağrılmak üzere tasarlanmıştır.
    """
    conn = None
    try:
        conn = get_db_connection() #
        cursor = conn.cursor()
        cursor.execute("""
            SELECT K.Ad, K.Soyad
            FROM Dosyalar D
            JOIN Kullanicilar K ON D.KullaniciId = K.KullaniciId
            WHERE D.DosyaId = ?
        """, (dosya_id,))
        user_row = cursor.fetchone()
        if user_row:
            return f"{user_row[0]} {user_row[1]}"
        return "Bilinmeyen Kullanıcı"
    except Exception as e:
        # current_app logger'ı bir Flask uygulama bağlamı gerektirir.
        # Eğer bu fonksiyon bir Celery task'ı içinde app context olmadan çağrılıyorsa,
        # standart Python logging kullanmak daha güvenli olabilir.
        # Veya task'a app context'i iletmek/oluşturmak gerekir.
        logger = current_app.logger if current_app else logging.getLogger(__name__)
        logger.error(f"Error in get_user_info_for_file_task for DosyaId {dosya_id}: {str(e)}")
        return "Hata Oluştu"
    finally:
        if conn:
            conn.close()

def get_similarity_for_pair_task(content_id, file1_id, file2_id):
    """
    Verilen içerik ID'si ve dosya ID çifti için benzerlik oranını döndürür.
    Bu fonksiyon Celery task içerisinde çağrılmak üzere tasarlanmıştır.
    """
    conn = None
    try:
        conn = get_db_connection() #
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 1 BenzerlikOrani
            FROM BenzerlikSonuclari
            WHERE IcerikId = ? AND
                  ((IlkDosyaId = ? AND IkinciDosyaId = ?) OR (IlkDosyaId = ? AND IkinciDosyaId = ?))
            ORDER BY SonucId DESC
        """, (content_id, file1_id, file2_id, file2_id, file1_id))
        sim_row = cursor.fetchone()
        return float(sim_row[0]) if sim_row and sim_row[0] is not None else 0.0
    except Exception as e:
        logger = current_app.logger if current_app else logging.getLogger(__name__)
        logger.error(f"Error in get_similarity_for_pair_task for ContentId {content_id}, F1:{file1_id}, F2:{file2_id}: {str(e)}")
        return 0.0
    finally:
        if conn:
            conn.close()

def generate_and_save_comparison_json(app_context, content_id, file1_info, file2_info, json_results_folder):
    """
    İki dosya arasında detaylı karşılaştırma yapar, JSON oluşturur, kaydeder ve veritabanına yolunu ekler.
    Bu fonksiyon Celery task tarafından çağrılır ve Flask uygulama bağlamını kullanır.
    """
    with app_context: # Flask uygulama bağlamını aktif et
        conn = None
        try:
            file1_id = file1_info['id']
            file1_path = file1_info['path']
            file2_id = file2_info['id']
            file2_path = file2_info['path']

            current_app.logger.debug(f"Async JSON generation for pair: ContentID {content_id}, File1_ID {file1_id}, File2_ID {file2_id}")

            if not os.path.isfile(file1_path) or not os.path.isfile(file2_path):
                current_app.logger.warning(f"Skipping JSON generation for pair in content_id {content_id}: File not found. F1: {file1_path}, F2: {file2_path}")
                return None

            task_start_time = time.time()

            user1_name = get_user_info_for_file_task(file1_id)
            user2_name = get_user_info_for_file_task(file2_id)
            similarity_score = get_similarity_for_pair_task(content_id, file1_id, file2_id)

            raw1 = read_text(file1_path) #
            raw2 = read_text(file2_path) #
            
            # MIN_MATCH_LEN config.py dosyasından veya varsayılan bir değerle alınır
            min_len_for_highlight = current_app.config.get('MIN_MATCH_LEN', 25)
            spans1, spans2 = get_difflib_spans(raw1, raw2, min_len=min_len_for_highlight) #

            words1_list = raw1.split()
            words2_list = raw2.split()
            set1_words, set2_words = set(words1_list), set(words2_list)
            matching_words_set = set1_words & set2_words

            comparison_result_data = {
                "text1": raw1.replace('\n', '<br>'),
                "text2": raw2.replace('\n', '<br>'),
                "raw_text1": raw1,
                "raw_text2": raw2,
                "user1": user1_name,
                "user2": user2_name,
                "similarity": similarity_score,
                "matchingWords": sorted(list(matching_words_set)),
                "totalWords1": len(words1_list),
                "totalWords2": len(words2_list),
                "matchingWordCount": len(matching_words_set),
                "uniqueWords1": len(set1_words - set2_words),
                "uniqueWords2": len(set2_words - set1_words),
                "matchSpans": [ # İstenen yeni parametre
                    {"start1": s1, "length": l1, "start2": s2, "length": l2}
                    for (s1, l1), (s2, l2) in zip(spans1, spans2)
                ],
                "diffSpans": [], 
                "timeElapsed": round(time.time() - task_start_time, 4),
                "timestamp": datetime.datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z",
                "content_id": str(content_id),
                "file1_id": str(file1_id),
                "file2_id": str(file2_id),
                "file1_path_original": file1_path,
                "file2_path_original": file2_path
            }
            
            json_filename = f"comparison_{content_id}_{file1_id}_{file2_id}_{uuid.uuid4()}.json"
            json_file_path = os.path.join(json_results_folder, json_filename)

            os.makedirs(json_results_folder, exist_ok=True)
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(comparison_result_data, f, ensure_ascii=False, indent=4)
            
            current_app.logger.debug(f"Saved detailed JSON for pair {file1_id}-{file2_id} to {json_file_path}")

            conn = get_db_connection() #
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DetailId FROM ComparisonJsonDetails 
                WHERE ContentId = ? AND 
                      ((FirstFileId = ? AND SecondFileId = ?) OR (FirstFileId = ? AND SecondFileId = ?))
            """, (content_id, file1_id, file2_id, file2_id, file1_id))
            existing_detail = cursor.fetchone()

            # Saat dilimi bilgisi olmayan (naive) datetime objesi oluştur
            naive_datetime_now = datetime.datetime.now(timezone.utc).replace(tzinfo=None)

            if existing_detail:
                cursor.execute("""
                    UPDATE ComparisonJsonDetails
                    SET JsonFilePath = ?, CreatedAt = ?
                    WHERE DetailId = ?
                """, (json_file_path, naive_datetime_now, existing_detail[0]))
                current_app.logger.info(f"Updated existing JSON detail (ID: {existing_detail[0]}) for pair {file1_id}-{file2_id}.")
            else:
                cursor.execute("""
                    INSERT INTO ComparisonJsonDetails (ContentId, FirstFileId, SecondFileId, JsonFilePath, CreatedAt)
                    VALUES (?, ?, ?, ?, ?)
                """, (content_id, file1_id, file2_id, json_file_path, naive_datetime_now))
                current_app.logger.info(f"Inserted new JSON detail for pair {file1_id}-{file2_id}.")
            
            conn.commit()
            return json_file_path

        except Exception as e:
            current_app.logger.error(f"Error in generate_and_save_comparison_json for ContentId {content_id}, F1:{file1_id}, F2:{file2_id}: {str(e)}", exc_info=True)
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

# Eğer Celery tasklarınız veya bu fonksiyonları çağıran başka yapılar varsa
# (örneğin process_single_comparison_task, start_async_json_generation_for_content)
# ve bu dosyada tanımlıysa, onların da `current_app.logger` kullanımı ve
# `app_context` yönetimi açısından gözden geçirilmesi gerekebilir.
# Bu örnek sadece `generate_and_save_comparison_json` ve yardımcı fonksiyonlarına odaklanmıştır.
# Standart Python logging modülünü import etmeyi unutmayın, eğer current_app yoksa kullanılacaksa:
import logging