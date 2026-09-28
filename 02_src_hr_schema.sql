-- HR-система: резюме, компетенции, заработная плата и премии.

DROP DATABASE IF EXISTS src_hr;
CREATE DATABASE src_hr
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;
USE src_hr;
SET NAMES utf8mb4;

-- Персоны. ФИО - в другом написании, чем в источнике 1.

CREATE TABLE person (
    person_id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    fio         VARCHAR(150) NOT NULL COMMENT 'ФИО в исходном (ненормализованном) виде',
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (person_id),
    KEY ix_person_fio (fio)
) ENGINE=InnoDB COMMENT='Персоны (источник 2)';

-- Резюме (1:1 с персоной)

CREATE TABLE resume (
    person_id               INT UNSIGNED  NOT NULL,
    position_title          VARCHAR(100)  NOT NULL,
    total_experience_years  DECIMAL(3,1)  NOT NULL,
    education               VARCHAR(200)  NOT NULL,
    summary                 TEXT          NOT NULL COMMENT 'Текст резюме',
    updated_at              DATE          NOT NULL,
    PRIMARY KEY (person_id),
    CONSTRAINT fk_resume_person FOREIGN KEY (person_id) REFERENCES person (person_id),
    CONSTRAINT ck_resume_exp CHECK (total_experience_years >= 0)
) ENGINE=InnoDB COMMENT='Резюме';

-- Компетенции и их уровень у конкретной персоны (M:N)

CREATE TABLE competency (
    competency_id  SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name           VARCHAR(80) NOT NULL,
    category       ENUM('hard','tool','soft') NOT NULL,
    PRIMARY KEY (competency_id),
    UNIQUE KEY uq_competency_name (name)
) ENGINE=InnoDB COMMENT='Справочник компетенций';

CREATE TABLE person_competency (
    person_id      INT UNSIGNED      NOT NULL,
    competency_id  SMALLINT UNSIGNED NOT NULL,
    level          TINYINT UNSIGNED  NOT NULL COMMENT 'Уровень владения 1..5',
    years_exp      DECIMAL(3,1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (person_id, competency_id),
    KEY ix_pc_competency (competency_id),
    CONSTRAINT fk_pc_person     FOREIGN KEY (person_id)     REFERENCES person (person_id),
    CONSTRAINT fk_pc_competency FOREIGN KEY (competency_id) REFERENCES competency (competency_id),
    CONSTRAINT ck_pc_level CHECK (level BETWEEN 1 AND 5)
) ENGINE=InnoDB COMMENT='Компетенции персон';

-- Заработная плата и премии (по кварталам). DECIMAL - точная арифметика для денег.

CREATE TABLE compensation (
    comp_id         INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    person_id       INT UNSIGNED      NOT NULL,
    period_year     SMALLINT UNSIGNED NOT NULL,
    period_quarter  TINYINT UNSIGNED  NOT NULL,
    salary          DECIMAL(12,2)     NOT NULL COMMENT 'Начислено оклада за квартал',
    bonus           DECIMAL(12,2)     NOT NULL DEFAULT 0 COMMENT 'Премия за квартал',
    currency        CHAR(3)           NOT NULL DEFAULT 'RUB',
    PRIMARY KEY (comp_id),
    UNIQUE KEY uq_comp_period (person_id, period_year, period_quarter),
    CONSTRAINT fk_comp_person FOREIGN KEY (person_id) REFERENCES person (person_id),
    CONSTRAINT ck_comp_q      CHECK (period_quarter BETWEEN 1 AND 4),
    CONSTRAINT ck_comp_amount CHECK (salary >= 0 AND bonus >= 0)
) ENGINE=InnoDB COMMENT='Зарплата и премии';
