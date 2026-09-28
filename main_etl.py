import logging
import os
import sys

try:
    import mysql.connector
    from mysql.connector import Error
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

from fio_match import parse_fio, Golden, resolve, finalize

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

from dotenv import load_dotenv

# Загружаем переменные из файла .env в системное окружение
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', '1234'),
    'charset': 'utf8mb4'
}

def get_connection(db_name: str):
    if not HAS_MYSQL:
        raise RuntimeError("mysql-connector-python не установлен в окружении.")
    config = DB_CONFIG.copy()
    config['database'] = db_name
    return mysql.connector.connect(**config)

def extract_data():
    """Извлекает сырые данные из src_projects и src_hr."""
    logging.info("=== ЭТАП 1: EXTRACT (Извлечение сырых данных) ===")
    raw_data = []

    try:
        # Извлекаем из Источника 1 (src_projects)
        with get_connection('src_projects') as conn_proj:
            with conn_proj.cursor() as cur:
                cur.execute("SELECT emp_id, full_name FROM employee ORDER BY emp_id")
                rows = cur.fetchall()
                logging.info(f"src_projects: прочитано {len(rows)} записей сотрудников.")
                for row in rows:
                    raw_data.append({
                        'source_id': 1,
                        'source_name': 'src_projects',
                        'source_pk': row[0],
                        'fio': row[1]
                    })

        # Извлекаем из Источника 2 (src_hr)
        with get_connection('src_hr') as conn_hr:
            with conn_hr.cursor() as cur:
                cur.execute("SELECT person_id, fio FROM person ORDER BY person_id")
                rows = cur.fetchall()
                logging.info(f"src_hr: прочитано {len(rows)} записей персон.")
                for row in rows:
                    raw_data.append({
                        'source_id': 2,
                        'source_name': 'src_hr',
                        'source_pk': row[0],
                        'fio': row[1]
                    })
    except Exception as e:
        logging.error(f"Ошибка при подключении к БД источников: {e}")
        raise

    logging.info(f"Всего извлечено записей из обоих источников: {len(raw_data)}")
    return raw_data

def transform_data(raw_data):
    logging.info("=== ЭТАП 2: TRANSFORM (Многокритериальная верификация и слияние) ===")
    goldens = []
    current_gid = 1
    review_queue = []

    for record in raw_data:
        raw_fio = record['fio']
        parsed = parse_fio(raw_fio)

        method, matched_golden, score, reason = resolve(parsed, goldens)

        if method == "new":
            new_golden = Golden(gid=current_gid)
            new_golden.add(key=record['source_pk'], p=parsed, method=method, score=1.0)
            new_golden.aliases = [{
                'source_id': record['source_id'],
                'source_name': record['source_name'],
                'source_pk': record['source_pk'],
                'raw_fio': raw_fio,
                'match_method': method,
                'match_score': 1.0,
                'details': reason
            }]
            goldens.append(new_golden)
            current_gid += 1
            logging.info(f"[NEW] Создан новый кандидат #{new_golden.gid}: «{raw_fio}» (структура: {parsed.pattern})")

        elif method in ["exact", "pattern", "fuzzy"]:
            matched_golden.add(key=record['source_pk'], p=parsed, method=method, score=score)
            matched_golden.aliases.append({
                'source_id': record['source_id'],
                'source_name': record['source_name'],
                'source_pk': record['source_pk'],
                'raw_fio': raw_fio,
                'match_method': method,
                'match_score': float(score),
                'details': reason
            })
            logging.info(
                f"[{method.upper()}] «{raw_fio}» объединен с Golden #{matched_golden.gid} «{matched_golden.label()}» "
                f"(оценка: {score:.2f}, {reason})"
            )

        elif method == "review":
            review_queue.append({
                'source_id': record['source_id'],
                'source_name': record['source_name'],
                'source_pk': record['source_pk'],
                'raw_fio': raw_fio,
                'candidate_gid': matched_golden.gid if matched_golden else None,
                'candidate_label': matched_golden.label() if matched_golden else None,
                'score': score,
                'reason': reason
            })
            logging.warning(f"[REVIEW] Спорная запись направлена дата-стюарду: «{raw_fio}» (оценка {score:.2f}) - {reason}")

    # Финализация (формируем данные под таблицу dim_person)
    transformed_records = []
    for g in goldens:
        f = finalize(g)
        in_proj = 1 if any(a['source_id'] == 1 for a in g.aliases) else 0
        in_hr = 1 if any(a['source_id'] == 2 for a in g.aliases) else 0

        transformed_records.append({
            'gid': g.gid,
            'canonical_fio': f['canonical'],
            'last_name': f['last'],
            'first_name': f['first'],
            'middle_name': f['middle'],
            'match_key': f['key'],
            'in_proj': in_proj,
            'in_hr': in_hr,
            'aliases': g.aliases
        })

    logging.info(
        f"Итог этапа TRANSFORM: Сформировано {len(transformed_records)} канонических Golden-персон, "
        f"в очереди на ручную проверку: {len(review_queue)} записей."
    )
    return transformed_records, review_queue

def load_data(transformed_data, review_queue):
    """Загружает проверенные сущности и алиасы в корпоративное ХД (dw_company)."""
    logging.info("=== ЭТАП 3: LOAD (Запись в ХД в рамках единой транзакции) ===")

    try:
        conn_dw = get_connection('dw_company')
        conn_dw.autocommit = False
        cur = conn_dw.cursor()

        # 1. Загрузка в dim_person и dim_person_alias
        for person in transformed_data:
            insert_person_sql = """
                INSERT INTO dim_person 
                (canonical_fio, last_name, first_name, middle_name, match_key, in_src_projects, in_src_hr) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON DUPLICATE KEY UPDATE 
                    canonical_fio = VALUES(canonical_fio),
                    in_src_projects = in_src_projects OR VALUES(in_src_projects),
                    in_src_hr = in_src_hr OR VALUES(in_src_hr)
            """
            cur.execute(insert_person_sql, (
                person['canonical_fio'],
                person['last_name'],
                person['first_name'],
                person['middle_name'],
                person['match_key'],
                person['in_proj'],
                person['in_hr']
            ))

            cur.execute("SELECT person_sk FROM dim_person WHERE match_key = %s", (person['match_key'],))
            person_sk = cur.fetchone()[0]

            for alias in person['aliases']:
                insert_alias_sql = """
                    INSERT INTO dim_person_alias 
                    (person_sk, source_id, source_pk, raw_fio, match_method, match_score) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        match_method = VALUES(match_method),
                        match_score = VALUES(match_score)
                """
                cur.execute(insert_alias_sql, (
                    person_sk,
                    alias['source_id'],
                    alias['source_pk'],
                    alias['raw_fio'],
                    alias['match_method'],
                    alias['match_score']
                ))

        # 2. Запись спорных записей в etl_review_queue (если таблица существует)
        if review_queue:
            try:
                for rev in review_queue:
                    cur.execute("""
                        INSERT INTO etl_review_queue
                        (source_id, source_pk, raw_fio, suggested_golden_id, score, review_reason, status)
                        VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                    """, (
                        rev['source_id'], rev['source_pk'], rev['raw_fio'],
                        rev['candidate_gid'], rev['score'], rev['reason']
                    ))
            except Exception as e_queue:
                logging.info(f"etl_review_queue пропущена или имеет другую схему: {e_queue}")

        conn_dw.commit()
        logging.info("Успешная загрузка данных в dw_company. Транзакция зафиксирована (COMMIT).")

    except Exception as e:
        if 'conn_dw' in locals() and conn_dw.is_connected():
            conn_dw.rollback()
        logging.error(f"Ошибка загрузки данных в ХД. Выполнен ROLLBACK. Причина: {e}")
        raise

    finally:
        if 'cur' in locals() and cur is not None:
            cur.close()
        if 'conn_dw' in locals() and conn_dw.is_connected():
            conn_dw.close()

if __name__ == "__main__":
    logging.info("Запуск многокритериального ETL-процесса")
    try:
        extracted = extract_data()
        transformed, reviews = transform_data(extracted)
        load_data(transformed, reviews)
        logging.info("ETL-процесс успешно завершен")
    except Exception as exc:
        logging.error(f"ETL-процесс завершился с ошибкой: {exc}")
