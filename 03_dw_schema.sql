-- ХРАНИЛИЩЕ ДАННЫХ: dw_company (звёздная схема)

DROP DATABASE IF EXISTS dw_company;
CREATE DATABASE dw_company
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;
USE dw_company;
SET NAMES utf8mb4;

-- Служебные: источники, журнал ETL, очередь ручной проверки

CREATE TABLE dim_source (
    source_id    TINYINT UNSIGNED NOT NULL,
    source_code  VARCHAR(30)      NOT NULL,
    description  VARCHAR(200)     NOT NULL,
    PRIMARY KEY (source_id),
    UNIQUE KEY uq_source_code (source_code)
) ENGINE=InnoDB COMMENT='Системы-источники';

INSERT INTO dim_source (source_id, source_code, description) VALUES
    (1, 'src_projects', 'Проекты, роли, технологический стек'),
    (2, 'src_hr',       'Резюме, компетенции, зарплата и премии');

CREATE TABLE etl_run_log (
    run_id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
    started_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at      DATETIME     NULL,
    status           ENUM('running','success','failed') NOT NULL DEFAULT 'running',
    persons_matched  INT UNSIGNED NOT NULL DEFAULT 0,
    persons_created  INT UNSIGNED NOT NULL DEFAULT 0,
    persons_review   INT UNSIGNED NOT NULL DEFAULT 0,
    message          VARCHAR(500) NULL,
    PRIMARY KEY (run_id)
) ENGINE=InnoDB COMMENT='Журнал запусков ETL';

-- Измерение «Человек» (золотая запись)

CREATE TABLE dim_person (
    person_sk        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    canonical_fio    VARCHAR(150) NOT NULL COMMENT 'Каноническое ФИО: Фамилия Имя Отчество',
    last_name        VARCHAR(80)  NOT NULL,
    first_name       VARCHAR(50)  NOT NULL,
    middle_name      VARCHAR(60)  NULL,
    match_key        VARCHAR(160) COLLATE utf8mb4_bin NOT NULL
                     COMMENT 'Нормализованный ключ: нижний регистр, ё->е, дефис->пробел',
    in_src_projects  TINYINT(1)   NOT NULL DEFAULT 0,
    in_src_hr        TINYINT(1)   NOT NULL DEFAULT 0,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (person_sk),
    UNIQUE KEY uq_person_match_key (match_key),
    KEY ix_person_last_first (last_name, first_name)
) ENGINE=InnoDB COMMENT='Единый справочник людей';

-- Соответствия: какая запись какого источника отнесена к какому человеку

CREATE TABLE dim_person_alias (
    alias_id       INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    person_sk      INT UNSIGNED     NOT NULL,
    source_id      TINYINT UNSIGNED NOT NULL,
    source_pk      INT UNSIGNED     NOT NULL COMMENT 'emp_id (src_projects) или person_id (src_hr)',
    raw_fio        VARCHAR(150)     NOT NULL COMMENT 'Исходное написание',
    match_method   VARCHAR(20)      NOT NULL COMMENT 'exact / pattern / fuzzy / manual / new',
    match_score    DECIMAL(5,4)     NOT NULL DEFAULT 1.0000,
    created_at     TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (alias_id),
    UNIQUE KEY uq_alias_source (source_id, source_pk),
    KEY ix_alias_person (person_sk),
    CONSTRAINT fk_alias_person FOREIGN KEY (person_sk) REFERENCES dim_person (person_sk),
    CONSTRAINT fk_alias_source FOREIGN KEY (source_id) REFERENCES dim_source (source_id)
) ENGINE=InnoDB COMMENT='Сопоставление записей источников и dim_person';

CREATE TABLE etl_review_queue (
    review_id           INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    run_id              INT UNSIGNED     NULL,
    source_id           TINYINT UNSIGNED NOT NULL,
    source_pk           INT UNSIGNED     NOT NULL,
    raw_fio             VARCHAR(150)     NOT NULL,
    candidate_person_sk INT UNSIGNED     NULL,
    match_score         DECIMAL(5,4)     NULL,
    reason              VARCHAR(200)     NOT NULL,
    status              ENUM('new','approved','rejected') NOT NULL DEFAULT 'new',
    created_at          TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (review_id),
    KEY ix_review_status (status),
    CONSTRAINT fk_review_source FOREIGN KEY (source_id) REFERENCES dim_source (source_id)
) ENGINE=InnoDB COMMENT='Спорные совпадения для ручной проверки дата-стюардом';

-- Резюме - отдельно от dim_person, чтобы «тяжёлый» TEXT не раздувал измерение

CREATE TABLE dim_person_resume (
    person_sk               INT UNSIGNED NOT NULL,
    position_title          VARCHAR(100) NOT NULL,
    total_experience_years  DECIMAL(3,1) NOT NULL,
    education               VARCHAR(200) NOT NULL,
    summary                 TEXT         NOT NULL,
    updated_at              DATE         NOT NULL,
    PRIMARY KEY (person_sk),
    CONSTRAINT fk_resume_dw_person FOREIGN KEY (person_sk) REFERENCES dim_person (person_sk)
) ENGINE=InnoDB COMMENT='Резюме сотрудников';

-- Прочие измерения
-- ---------------------------------------------------------------------
CREATE TABLE dim_role (
    role_sk       SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    src_role_id   SMALLINT UNSIGNED NOT NULL,
    role_name     VARCHAR(80)       NOT NULL,
    description   VARCHAR(500)      NOT NULL,
    PRIMARY KEY (role_sk),
    UNIQUE KEY uq_dim_role_src (src_role_id),
    UNIQUE KEY uq_dim_role_name (role_name)
) ENGINE=InnoDB COMMENT='Роли в проекте';

CREATE TABLE dim_project (
    project_sk      SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    src_project_id  SMALLINT UNSIGNED NOT NULL,
    project_name    VARCHAR(150)      NOT NULL,
    customer        VARCHAR(120)      NOT NULL,
    description     TEXT              NOT NULL,
    tech_stack      VARCHAR(500)      NOT NULL DEFAULT '' COMMENT 'Денормализованная строка стека для отчётов',
    start_date      DATE              NOT NULL,
    end_date        DATE              NULL,
    status          ENUM('planned','active','on_hold','completed') NOT NULL,
    PRIMARY KEY (project_sk),
    UNIQUE KEY uq_dim_project_src (src_project_id),
    KEY ix_dim_project_status (status)
) ENGINE=InnoDB COMMENT='Проекты';

CREATE TABLE dim_technology (
    technology_sk  SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    src_tech_id    SMALLINT UNSIGNED NOT NULL,
    tech_name      VARCHAR(60)       NOT NULL,
    category       VARCHAR(40)       NOT NULL,
    PRIMARY KEY (technology_sk),
    UNIQUE KEY uq_dim_tech_src (src_tech_id),
    UNIQUE KEY uq_dim_tech_name (tech_name)
) ENGINE=InnoDB COMMENT='Технологии';

CREATE TABLE dim_competency (
    competency_sk      SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    src_competency_id  SMALLINT UNSIGNED NOT NULL,
    name               VARCHAR(80)       NOT NULL,
    category           ENUM('hard','tool','soft') NOT NULL,
    PRIMARY KEY (competency_sk),
    UNIQUE KEY uq_dim_comp_src (src_competency_id),
    UNIQUE KEY uq_dim_comp_name (name)
) ENGINE=InnoDB COMMENT='Компетенции';

-- Календарь: ключ YYYYMMDD (INT UNSIGNED = 4 байта, читаем без JOIN)
CREATE TABLE dim_date (
    date_key     INT UNSIGNED      NOT NULL,
    full_date    DATE              NOT NULL,
    year_num     SMALLINT UNSIGNED NOT NULL,
    quarter_num  TINYINT UNSIGNED  NOT NULL,
    month_num    TINYINT UNSIGNED  NOT NULL,
    day_num      TINYINT UNSIGNED  NOT NULL,
    weekday_num  TINYINT UNSIGNED  NOT NULL COMMENT '1 = понедельник',
    is_weekend   TINYINT(1)        NOT NULL,
    PRIMARY KEY (date_key),
    UNIQUE KEY uq_dim_date_full (full_date),
    KEY ix_dim_date_ym (year_num, month_num)
) ENGINE=InnoDB COMMENT='Календарь';

SET SESSION cte_max_recursion_depth = 5000;
INSERT INTO dim_date (date_key, full_date, year_num, quarter_num, month_num, day_num, weekday_num, is_weekend)
WITH RECURSIVE d AS (
    SELECT DATE('2020-01-01') AS dt
    UNION ALL
    SELECT dt + INTERVAL 1 DAY FROM d WHERE dt < DATE('2030-12-31')
)
SELECT CAST(DATE_FORMAT(dt, '%Y%m%d') AS UNSIGNED),
       dt, YEAR(dt), QUARTER(dt), MONTH(dt), DAY(dt), WEEKDAY(dt) + 1, WEEKDAY(dt) >= 5
FROM d;

-- Мост «проект - технология» (M:N)

CREATE TABLE bridge_project_technology (
    project_sk     SMALLINT UNSIGNED NOT NULL,
    technology_sk  SMALLINT UNSIGNED NOT NULL,
    is_core        TINYINT(1)        NOT NULL DEFAULT 0,
    PRIMARY KEY (project_sk, technology_sk),
    KEY ix_bpt_tech (technology_sk),
    CONSTRAINT fk_bpt_project FOREIGN KEY (project_sk)    REFERENCES dim_project (project_sk),
    CONSTRAINT fk_bpt_tech    FOREIGN KEY (technology_sk) REFERENCES dim_technology (technology_sk)
) ENGINE=InnoDB COMMENT='Технологический стек проекта';

-- Факты

CREATE TABLE fact_assignment (
    assignment_sk      INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    src_assignment_id  INT UNSIGNED      NOT NULL,
    person_sk          INT UNSIGNED      NOT NULL,
    project_sk         SMALLINT UNSIGNED NOT NULL,
    role_sk            SMALLINT UNSIGNED NOT NULL,
    date_from_key      INT UNSIGNED      NOT NULL,
    date_to_key        INT UNSIGNED      NULL,
    allocation_pct     TINYINT UNSIGNED  NOT NULL,
    PRIMARY KEY (assignment_sk),
    UNIQUE KEY uq_fact_assign_src (src_assignment_id),
    KEY ix_fa_person_project (person_sk, project_sk),
    KEY ix_fa_project (project_sk),
    KEY ix_fa_role (role_sk),
    KEY ix_fa_date_from (date_from_key),
    CONSTRAINT fk_fa_person  FOREIGN KEY (person_sk)     REFERENCES dim_person (person_sk),
    CONSTRAINT fk_fa_project FOREIGN KEY (project_sk)    REFERENCES dim_project (project_sk),
    CONSTRAINT fk_fa_role    FOREIGN KEY (role_sk)       REFERENCES dim_role (role_sk),
    CONSTRAINT fk_fa_dfrom   FOREIGN KEY (date_from_key) REFERENCES dim_date (date_key),
    CONSTRAINT fk_fa_dto     FOREIGN KEY (date_to_key)   REFERENCES dim_date (date_key)
) ENGINE=InnoDB COMMENT='Факт: участие в проектах';

CREATE TABLE fact_compensation (
    comp_sk           INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    person_sk         INT UNSIGNED      NOT NULL,
    period_start_key  INT UNSIGNED      NOT NULL COMMENT 'Первый день квартала (YYYYMMDD)',
    period_year       SMALLINT UNSIGNED NOT NULL,
    period_quarter    TINYINT UNSIGNED  NOT NULL,
    salary            DECIMAL(12,2)     NOT NULL,
    bonus             DECIMAL(12,2)     NOT NULL,
    total_pay         DECIMAL(13,2) AS (salary + bonus) STORED,
    currency          CHAR(3)           NOT NULL,
    PRIMARY KEY (comp_sk),
    UNIQUE KEY uq_fc_person_period (person_sk, period_year, period_quarter),
    KEY ix_fc_period (period_year, period_quarter),
    KEY ix_fc_date (period_start_key),
    CONSTRAINT fk_fc_person FOREIGN KEY (person_sk)        REFERENCES dim_person (person_sk),
    CONSTRAINT fk_fc_date   FOREIGN KEY (period_start_key) REFERENCES dim_date (date_key)
) ENGINE=InnoDB COMMENT='Факт: зарплата и премии по кварталам';

CREATE TABLE fact_person_competency (
    person_sk      INT UNSIGNED      NOT NULL,
    competency_sk  SMALLINT UNSIGNED NOT NULL,
    level          TINYINT UNSIGNED  NOT NULL,
    years_exp      DECIMAL(3,1)      NOT NULL,
    PRIMARY KEY (person_sk, competency_sk),
    KEY ix_fpc_competency (competency_sk, level),
    CONSTRAINT fk_fpc_person FOREIGN KEY (person_sk)     REFERENCES dim_person (person_sk),
    CONSTRAINT fk_fpc_comp   FOREIGN KEY (competency_sk) REFERENCES dim_competency (competency_sk)
) ENGINE=InnoDB COMMENT='Факт: уровень компетенций';

