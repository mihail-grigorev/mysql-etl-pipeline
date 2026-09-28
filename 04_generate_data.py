from __future__ import annotations

import csv
import os
import random
from collections import Counter
from datetime import date, timedelta

try:
    import pymysql
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

from fio_lib import VARIANTS, assign_variants, generate_people, render

SEED = int(os.getenv("SEED", "42"))
N_TOTAL, N_BOTH, N_ONLY_PROJ, N_ONLY_HR = 60, 42, 9, 9
REF_DATE = date(2026, 9, 20)          # «сегодня» для генерации дат
OUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ground_truth.csv")

# ======================================================================
# Справочные данные
# ======================================================================
ROLES = [
    ("Руководитель проекта", "Отвечает за сроки, бюджет и риски проекта, координирует команду и общается с заказчиком."),
    ("Scrum-мастер", "Организует процессы Scrum, устраняет препятствия команды, следит за метриками потока."),
    ("Бизнес-аналитик", "Выявляет бизнес-потребности, формализует требования, описывает бизнес-процессы в BPMN."),
    ("Системный аналитик", "Проектирует интеграции и API, пишет техническую спецификацию и модели данных."),
    ("Архитектор решений", "Определяет архитектуру системы, выбирает технологический стек, отвечает за нефункциональные требования."),
    ("Backend-разработчик", "Разрабатывает серверную часть: бизнес-логику, API, работу с БД и очередями сообщений."),
    ("Frontend-разработчик", "Разрабатывает клиентскую часть: интерфейсы, состояние приложения, интеграцию с API."),
    ("Fullstack-разработчик", "Разрабатывает и клиентскую, и серверную части продукта."),
    ("QA-инженер", "Проектирует тесты, проводит ручное и автоматизированное тестирование, ведёт дефекты."),
    ("DevOps-инженер", "Строит CI/CD, инфраструктуру как код, мониторинг и эксплуатацию окружений."),
    ("Data Engineer", "Проектирует потоки данных и хранилища, разрабатывает ETL/ELT-пайплайны."),
    ("Дизайнер UX/UI", "Проводит исследования пользователей, проектирует прототипы и дизайн интерфейсов."),
    ("Технический писатель", "Готовит пользовательскую и техническую документацию проекта."),
]

TECHNOLOGIES = [
    ("Java", "Язык"), ("Kotlin", "Язык"), ("Swift", "Язык"), ("Go", "Язык"), ("Python", "Язык"),
    ("C#", "Язык"), ("C++", "Язык"), ("TypeScript", "Язык"), ("JavaScript", "Язык"), ("Node.js", "Платформа"),
    ("Spring Boot", "Фреймворк"), ("Django", "Фреймворк"), ("FastAPI", "Фреймворк"), (".NET", "Платформа"),
    ("React", "Фреймворк"), ("Vue.js", "Фреймворк"), ("Angular", "Фреймворк"), ("Rasa", "Фреймворк"),
    ("PyTorch", "ML"),
    ("PostgreSQL", "СУБД"), ("MySQL", "СУБД"), ("MS SQL Server", "СУБД"), ("MongoDB", "СУБД"),
    ("ClickHouse", "СУБД"), ("InfluxDB", "СУБД"), ("Redis", "СУБД"), ("Elasticsearch", "Поиск"),
    ("Kafka", "Брокер сообщений"), ("RabbitMQ", "Брокер сообщений"), ("MQTT", "Протокол"), ("gRPC", "Протокол"),
    ("Docker", "Инфраструктура"), ("Kubernetes", "Инфраструктура"), ("Terraform", "Инфраструктура"),
    ("Ansible", "Инфраструктура"), ("AWS", "Облако"), ("SAP", "Платформа"),
    ("Airflow", "Аналитика"), ("dbt", "Аналитика"), ("Superset", "Аналитика"), ("Grafana", "Мониторинг"),
    ("MLflow", "ML"), ("Telegram Bot API", "Интеграция"),
]

PROJECTS = [
    ("Интернет-банк «Мой Банк»", "АО «Мой Банк»",
     "Веб- и мобильный интернет-банк для физических лиц: платежи, переводы, витрина вкладов и персональные предложения. "
     "Микросервисная архитектура, событийный обмен между сервисами, требования PCI DSS.",
     date(2024, 2, 1), None, "active",
     ["Java", "Spring Boot", "PostgreSQL", "Kafka", "React", "Docker", "Kubernetes"]),
    ("CRM «Ритейл-360»", "ООО «Торговая сеть Север»",
     "CRM для розничной сети: единая карточка клиента, программа лояльности, сегментация и рассылки.",
     date(2023, 9, 1), date(2025, 3, 31), "completed",
     ["Python", "Django", "MySQL", "Redis", "Vue.js", "Docker"]),
    ("Платформа аналитики продаж", "ПАО «Гипермаркет»",
     "Корпоративное хранилище и BI-витрины по продажам: загрузка из кассовых систем, расчёт KPI, дашборды для руководителей.",
     date(2024, 5, 15), None, "active",
     ["Python", "Airflow", "ClickHouse", "dbt", "Superset", "Docker"]),
    ("Мобильное приложение «Быстрый курьер»", "ООО «Быстрая доставка»",
     "Мобильные приложения для клиентов и курьеров, маршрутизация заказов, трекинг в реальном времени.",
     date(2023, 11, 1), date(2025, 6, 30), "completed",
     ["Kotlin", "Swift", "Go", "PostgreSQL", "gRPC", "Redis"]),
    ("HR-портал «Люди»", "АО «Промышленные технологии»",
     "Корпоративный портал: кадровый документооборот, заявки сотрудников, онбординг, оценка эффективности.",
     date(2024, 9, 1), date(2026, 3, 31), "completed",
     ["C#", ".NET", "MS SQL Server", "Angular", "Docker"]),
    ("Мониторинг IoT-датчиков", "ООО «Умный Завод»",
     "Сбор и визуализация телеметрии с промышленных датчиков, правила оповещений, прогноз отказов оборудования.",
     date(2025, 1, 10), None, "active",
     ["C++", "MQTT", "InfluxDB", "Grafana", "Docker", "Kubernetes"]),
    ("B2B-маркетплейс «Оптовик»", "ООО «Оптовик Групп»",
     "Маркетплейс для оптовых закупок: каталог, персональные цены, заказы, интеграция с ERP поставщиков.",
     date(2025, 3, 1), None, "active",
     ["Node.js", "TypeScript", "MongoDB", "Elasticsearch", "RabbitMQ", "React"]),
    ("ML-сервис рекомендаций", "ООО «Медиа Плюс»",
     "Сервис персональных рекомендаций контента: обучение моделей, онлайн-инференс, A/B-тестирование.",
     date(2025, 6, 1), None, "active",
     ["Python", "PyTorch", "FastAPI", "MLflow", "Kubernetes", "PostgreSQL"]),
    ("Миграция ERP в облако", "АО «Стальпром»",
     "Перенос ERP-системы в облачную инфраструктуру, автоматизация развёртывания и резервного копирования.",
     date(2024, 1, 15), date(2025, 12, 31), "completed",
     ["SAP", "AWS", "Terraform", "Ansible"]),
    ("Чат-бот поддержки клиентов", "АО «ТелекомПлюс»",
     "Чат-бот первой линии поддержки: распознавание намерений, сценарии диалога, передача оператору.",
     date(2026, 2, 1), None, "active",
     ["Python", "Rasa", "PostgreSQL", "Telegram Bot API", "Docker"]),
]

COMPETENCIES = [
    ("Java", "hard"), ("Python", "hard"), ("SQL", "hard"), ("JavaScript", "hard"), ("TypeScript", "hard"),
    ("Spring Boot", "hard"), ("React", "hard"), ("Vue.js", "hard"), ("HTML/CSS", "hard"), ("Kafka", "hard"),
    ("PostgreSQL", "hard"), ("ClickHouse", "hard"), ("Airflow", "hard"), ("dbt", "hard"), ("Spark", "hard"),
    ("Kubernetes", "hard"), ("Docker", "hard"), ("Terraform", "hard"), ("Ansible", "hard"), ("Linux", "hard"),
    ("AWS", "hard"), ("Selenium", "hard"), ("Тестирование ПО", "hard"), ("BPMN", "hard"), ("UML", "hard"),
    ("Разработка требований", "hard"), ("UX-исследования", "hard"), ("Прототипирование", "hard"),
    ("Git", "tool"), ("CI/CD", "tool"), ("Postman", "tool"), ("Figma", "tool"), ("Confluence/Jira", "tool"),
    ("Коммуникации", "soft"), ("Управление проектами", "soft"), ("Scrum/Kanban", "soft"),
    ("Управление рисками", "soft"), ("Английский язык", "soft"), ("Наставничество", "soft"),
]
GENERAL_COMPS = ["Git", "Английский язык", "Коммуникации", "Наставничество", "Confluence/Jira"]

SPECS = {
    "backend":  (25, "Backend-разработчик", ["Backend-разработчик", "Backend-разработчик", "Архитектор решений", "Fullstack-разработчик"],
                 ["Java", "Python", "SQL", "PostgreSQL", "Docker", "Kafka", "Spring Boot"], (180_000, 380_000)),
    "frontend": (12, "Frontend-разработчик", ["Frontend-разработчик", "Fullstack-разработчик"],
                 ["JavaScript", "TypeScript", "React", "Vue.js", "HTML/CSS"], (150_000, 320_000)),
    "qa":       (12, "QA-инженер", ["QA-инженер"],
                 ["Тестирование ПО", "Selenium", "Postman", "SQL", "Python"], (120_000, 250_000)),
    "devops":   (9, "DevOps-инженер", ["DevOps-инженер"],
                 ["Docker", "Kubernetes", "Terraform", "Ansible", "Linux", "CI/CD", "AWS"], (200_000, 400_000)),
    "data":     (10, "Data Engineer", ["Data Engineer"],
                 ["Python", "SQL", "Airflow", "ClickHouse", "dbt", "Spark", "PostgreSQL"], (200_000, 380_000)),
    "analyst":  (14, "Аналитик", ["Бизнес-аналитик", "Системный аналитик", "Технический писатель"],
                 ["BPMN", "UML", "SQL", "Разработка требований", "Postman"], (150_000, 300_000)),
    "design":   (6, "Дизайнер UX/UI", ["Дизайнер UX/UI"],
                 ["Figma", "UX-исследования", "Прототипирование", "HTML/CSS"], (130_000, 280_000)),
    "pm":       (12, "Руководитель проектов", ["Руководитель проекта", "Scrum-мастер"],
                 ["Управление проектами", "Scrum/Kanban", "Управление рисками", "Коммуникации"], (250_000, 450_000)),
}
EDUCATION = [
    "МГУ им. М.В. Ломоносова, факультет ВМК", "МГТУ им. Н.Э. Баумана, ИУ", "НИУ ВШЭ, факультет компьютерных наук",
    "ИТМО, факультет программной инженерии", "СПбГУ, математико-механический факультет", "МИРЭА, ИТ",
    "Финансовый университет при Правительстве РФ", "Университет Иннополис",
]
SUMMARY_EXTRA = [
    "Есть опыт наставничества и проведения технических интервью.",
    "Участвовал в проектах для банковского и ритейл-секторов.",
    "Работаю в распределённых командах по Scrum.",
    "Имею опыт выступлений на профессиональных конференциях.",
    "Готов к участию в нескольких проектах одновременно.",
]

from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()

# Флаг доступности библиотеки
HAS_PYMYSQL = True

def connect(db: str):
    if not HAS_PYMYSQL:
        return None
    
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "1234")
    
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor
    )

def reset_tables(cur, tables):
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for t in tables:
        cur.execute(f"TRUNCATE TABLE `{t}`")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")

def rand_date(rng: random.Random, a: date, b: date) -> date:
    return a + timedelta(days=rng.randint(0, max(0, (b - a).days)))

def fill_projects_db(rng, people, specs, raw_names):
    try:
        conn = connect("src_projects")
        if not conn:
            return {i: i + 1 for i in raw_names}
        cur = conn.cursor()
        reset_tables(cur, ["assignment", "project_technology", "project", "technology", "role", "employee"])

        role_id = {}
        for name, desc in ROLES:
            cur.execute("INSERT INTO role (role_name, description) VALUES (%s,%s)", (name, desc))
            role_id[name] = cur.lastrowid

        tech_id = {}
        for name, cat in TECHNOLOGIES:
            cur.execute("INSERT INTO technology (tech_name, category) VALUES (%s,%s)", (name, cat))
            tech_id[name] = cur.lastrowid

        projects = {}
        for name, customer, desc, d1, d2, status, stack in PROJECTS:
            cur.execute(
                "INSERT INTO project (project_name, customer, description, start_date, end_date, status) "
                "VALUES (%s,%s,%s,%s,%s,%s)", (name, customer, desc, d1, d2, status))
            pid = cur.lastrowid
            projects[pid] = (d1, d2)
            for i, t in enumerate(stack):
                cur.execute("INSERT INTO project_technology (project_id, tech_id, is_core) VALUES (%s,%s,%s)",
                            (pid, tech_id[t], 1 if i < 3 else 0))

        emp_id = {}
        for idx, raw in raw_names.items():
            cur.execute("INSERT INTO employee (full_name) VALUES (%s)", (raw,))
            emp_id[idx] = cur.lastrowid

        n_assign = 0
        pids = list(projects)
        for idx, eid in emp_id.items():
            remaining = 100
            for pid in rng.sample(pids, k=rng.choice([1, 2, 2, 3])):
                options = [a for a in (20, 30, 40, 50, 60, 80, 100) if a <= remaining]
                if not options:
                    break
                alloc = rng.choice(options)
                remaining -= alloc
                d1, d2 = projects[pid]
                bound = d2 or REF_DATE
                date_from = rand_date(rng, d1, bound - timedelta(days=60))
                if d2 is not None:
                    date_to = rand_date(rng, date_from + timedelta(days=30), d2)
                else:
                    date_to = None if rng.random() < 0.7 else rand_date(rng, date_from + timedelta(days=30), REF_DATE)
                role = rng.choice(SPECS[specs[idx]][2])
                cur.execute(
                    "INSERT INTO assignment (emp_id, project_id, role_id, allocation_pct, date_from, date_to) "
                    "VALUES (%s,%s,%s,%s,%s,%s)", (eid, pid, role_id[role], alloc, date_from, date_to))
                n_assign += 1
        conn.commit()
        conn.close()
        print(f"src_projects: сотрудников={len(emp_id)}, проектов={len(projects)}, "
              f"ролей={len(role_id)}, технологий={len(tech_id)}, назначений={n_assign}")
        return emp_id
    except Exception as e:
        print(f"src_projects DB unavailable: {e}. Generating mock IDs.")
        return {i: i + 1 for i in raw_names}

def fill_hr_db(rng, people, specs, raw_names):
    try:
        conn = connect("src_hr")
        if not conn:
            return {i: i + 1 for i in raw_names}
        cur = conn.cursor()
        reset_tables(cur, ["compensation", "person_competency", "competency", "resume", "person"])

        comp_id = {}
        for name, cat in COMPETENCIES:
            cur.execute("INSERT INTO competency (name, category) VALUES (%s,%s)", (name, cat))
            comp_id[name] = cur.lastrowid

        person_id = {}
        n_pc = n_comp = 0
        for idx, raw in raw_names.items():
            cur.execute("INSERT INTO person (fio) VALUES (%s)", (raw,))
            pid = cur.lastrowid
            person_id[idx] = pid

            _, title, _, spec_comps, (lo, hi) = SPECS[specs[idx]]
            exp = round(rng.uniform(1, 15), 1)
            grade = "Junior" if exp < 3 else "Middle" if exp < 6 else "Senior"

            chosen = [c for c in spec_comps if rng.random() < 0.85] or spec_comps[:3]
            chosen += rng.sample(GENERAL_COMPS, k=rng.randint(1, 2))
            chosen = list(dict.fromkeys(chosen))
            for c in chosen:
                level = max(1, min(5, round(exp / 3 + rng.uniform(-1, 1.5))))
                years = round(rng.uniform(0.5, exp), 1)
                cur.execute("INSERT INTO person_competency (person_id, competency_id, level, years_exp) "
                            "VALUES (%s,%s,%s,%s)", (pid, comp_id[c], level, years))
                n_pc += 1

            summary = (f"{grade} {title} с опытом {exp} лет. Ключевые компетенции: {', '.join(chosen[:5])}. "
                       f"{rng.choice(SUMMARY_EXTRA)}")
            cur.execute(
                "INSERT INTO resume (person_id, position_title, total_experience_years, education, summary, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (pid, f"{grade} {title}", exp, rng.choice(EDUCATION), summary,
                 rand_date(rng, REF_DATE - timedelta(days=365), REF_DATE)))

            monthly = round(rng.randint(lo, hi) / 1000) * 1000
            periods = [(2025, 1), (2025, 2), (2025, 3), (2025, 4), (2026, 1), (2026, 2)]
            for (y, q) in periods[rng.choice([0, 0, 1, 2]):]:
                growth = 1.0 if y == 2025 else 1.06
                salary = round(monthly * 3 * growth)
                bonus = round(salary * rng.choice([0, 0, 0.05, 0.1, 0.15, 0.25]), -2)
                cur.execute("INSERT INTO compensation (person_id, period_year, period_quarter, salary, bonus, currency) "
                            "VALUES (%s,%s,%s,%s,%s,'RUB')", (pid, y, q, salary, bonus))
                n_comp += 1
        conn.commit()
        conn.close()
        print(f"src_hr: персон={len(person_id)}, компетенций={len(comp_id)}, "
              f"записей person_competency={n_pc}, записей compensation={n_comp}")
        return person_id
    except Exception as e:
        print(f"src_hr DB unavailable: {e}. Generating mock IDs.")
        return {i: i + 1 for i in raw_names}

def main():
    rng = random.Random(SEED)

    tech_names = {t for t, _ in TECHNOLOGIES}
    comp_names = {c for c, _ in COMPETENCIES}
    role_names = {r for r, _ in ROLES}
    for pr in PROJECTS:
        assert set(pr[6]) <= tech_names, pr[0]
    for k, v in SPECS.items():
        assert set(v[3]) <= comp_names and set(v[2]) <= role_names, k
    assert set(GENERAL_COMPS) <= comp_names
    assert N_BOTH + N_ONLY_PROJ + N_ONLY_HR == N_TOTAL

    people = generate_people(N_TOTAL, rng)
    spec_keys = list(SPECS)
    specs = [rng.choices(spec_keys, weights=[SPECS[k][0] for k in spec_keys])[0] for _ in people]

    doubles = [i for i, p in enumerate(people) if "-" in p.last or p.has_foreign_prefix]
    others = [i for i in range(len(people)) if i not in doubles]
    rng.shuffle(others)
    order = doubles + others
    both = set(order[:N_BOTH])
    only_proj = set(order[N_BOTH:N_BOTH + N_ONLY_PROJ])
    only_hr = set(order[N_BOTH + N_ONLY_PROJ:])
    in_proj, in_hr = both | only_proj, both | only_hr

    slots = [(i, 0) for i in sorted(in_proj)] + [(i, 1) for i in sorted(in_hr)]
    variants = assign_variants(slots, people, rng)
    raw_proj = {i: render(variants[(i, 0)], people[i], rng) for i in sorted(in_proj)}
    raw_hr = {i: render(variants[(i, 1)], people[i], rng) for i in sorted(in_hr)}

    emp_id = fill_projects_db(rng, people, specs, raw_proj)
    person_id = fill_hr_db(rng, people, specs, raw_hr)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["true_id", "canonical_fio", "src_projects_emp_id", "src_projects_raw", "src_projects_variant",
                    "src_hr_person_id", "src_hr_raw", "src_hr_variant"])
        for i, p in enumerate(people):
            w.writerow([
                i + 1, p.canonical,
                emp_id.get(i, ""), repr(raw_proj[i])[1:-1] if i in raw_proj else "",
                variants[(i, 0)].code if i in raw_proj else "",
                person_id.get(i, ""), repr(raw_hr[i])[1:-1] if i in raw_hr else "",
                variants[(i, 1)].code if i in raw_hr else "",
            ])
    used = Counter(v.code for v in variants.values())
    print(f"Использовано типов написаний: {len(used)} из {len(VARIANTS)}")
    for code, cnt in used.most_common():
        print(f"  - {code}: {cnt}")
    print("Эталон сопоставления сохранен:", OUT_CSV)
    print(f"В обоих источниках: {len(both)}, только src_projects: {len(only_proj)}, только src_hr: {len(only_hr)}")

if __name__ == "__main__":
    main()
