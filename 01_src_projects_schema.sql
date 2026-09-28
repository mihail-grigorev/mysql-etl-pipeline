-- Система учёта проектов: сотрудники, роли в проектах, проекты, технологический стек.
DROP DATABASE IF EXISTS src_projects;
CREATE DATABASE src_projects
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;
USE src_projects;
SET NAMES utf8mb4;

-- Сотрудники. ФИО хранится «как ввели» - в разных написаниях.
CREATE TABLE employee (
    emp_id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
    full_name   VARCHAR(150) NOT NULL COMMENT 'ФИО в исходном (ненормализованном) виде',
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (emp_id),
    KEY ix_employee_full_name (full_name)
) ENGINE=InnoDB COMMENT='Сотрудники (источник 1)';

-- Справочник ролей в проекте

CREATE TABLE role (
    role_id      SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    role_name    VARCHAR(80)  NOT NULL,
    description  VARCHAR(500) NOT NULL COMMENT 'Описание зоны ответственности роли',
    PRIMARY KEY (role_id),
    UNIQUE KEY uq_role_name (role_name)
) ENGINE=InnoDB COMMENT='Роли в проекте';

-- Проекты

CREATE TABLE project (
    project_id    SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    project_name  VARCHAR(150) NOT NULL,
    customer      VARCHAR(120) NOT NULL,
    description   TEXT         NOT NULL COMMENT 'Описание проекта',
    start_date    DATE         NOT NULL,
    end_date      DATE         NULL,
    status        ENUM('planned','active','on_hold','completed') NOT NULL DEFAULT 'active',
    PRIMARY KEY (project_id),
    UNIQUE KEY uq_project_name (project_name),
    KEY ix_project_status (status),
    CONSTRAINT ck_project_dates CHECK (end_date IS NULL OR end_date >= start_date)
) ENGINE=InnoDB COMMENT='Проекты';


-- Технологии и технологический стек проекта (связь M:N)

CREATE TABLE technology (
    tech_id    SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    tech_name  VARCHAR(60) NOT NULL,
    category   VARCHAR(40) NOT NULL COMMENT 'Язык, фреймворк, СУБД, инфраструктура и т.п.',
    PRIMARY KEY (tech_id),
    UNIQUE KEY uq_tech_name (tech_name)
) ENGINE=InnoDB COMMENT='Справочник технологий';

CREATE TABLE project_technology (
    project_id  SMALLINT UNSIGNED NOT NULL,
    tech_id     SMALLINT UNSIGNED NOT NULL,
    is_core     TINYINT(1)        NOT NULL DEFAULT 0 COMMENT '1 - ключевая технология проекта',
    PRIMARY KEY (project_id, tech_id),
    KEY ix_pt_tech (tech_id),
    CONSTRAINT fk_pt_project FOREIGN KEY (project_id) REFERENCES project (project_id),
    CONSTRAINT fk_pt_tech    FOREIGN KEY (tech_id)    REFERENCES technology (tech_id)
) ENGINE=InnoDB COMMENT='Технологический стек проекта';


-- Участие сотрудника в проекте в определённой роли

CREATE TABLE assignment (
    assignment_id   INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    emp_id          INT UNSIGNED      NOT NULL,
    project_id      SMALLINT UNSIGNED NOT NULL,
    role_id         SMALLINT UNSIGNED NOT NULL,
    allocation_pct  TINYINT UNSIGNED  NOT NULL DEFAULT 100 COMMENT 'Загрузка, %',
    date_from       DATE              NOT NULL,
    date_to         DATE              NULL,
    PRIMARY KEY (assignment_id),
    UNIQUE KEY uq_assignment (emp_id, project_id, role_id, date_from),
    KEY ix_assignment_project (project_id),
    KEY ix_assignment_role (role_id),
    CONSTRAINT fk_assign_emp     FOREIGN KEY (emp_id)     REFERENCES employee (emp_id),
    CONSTRAINT fk_assign_project FOREIGN KEY (project_id) REFERENCES project (project_id),
    CONSTRAINT fk_assign_role    FOREIGN KEY (role_id)    REFERENCES role (role_id),
    CONSTRAINT ck_assign_pct     CHECK (allocation_pct BETWEEN 1 AND 100),
    CONSTRAINT ck_assign_dates   CHECK (date_to IS NULL OR date_to >= date_from)
) ENGINE=InnoDB COMMENT='Назначения сотрудников на проекты';
