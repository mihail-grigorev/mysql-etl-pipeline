-- Контрольные запросы после наполнения источников
SELECT 'src_projects.employee' AS tbl, COUNT(*) AS cnt FROM src_projects.employee
UNION ALL SELECT 'src_projects.project',     COUNT(*) FROM src_projects.project
UNION ALL SELECT 'src_projects.assignment',  COUNT(*) FROM src_projects.assignment
UNION ALL SELECT 'src_hr.person',            COUNT(*) FROM src_hr.person
UNION ALL SELECT 'src_hr.person_competency', COUNT(*) FROM src_hr.person_competency
UNION ALL SELECT 'src_hr.compensation',      COUNT(*) FROM src_hr.compensation;

-- Примеры записи ФИО в источниках (эталон соответствия - в ground_truth.csv)
SELECT 'src_projects' AS src, emp_id AS id, full_name AS raw_fio FROM src_projects.employee
UNION ALL
SELECT 'src_hr', person_id, fio FROM src_hr.person
ORDER BY 1, 2 LIMIT 20;

-- Проекты и их технологический стек
SELECT p.project_name,
       GROUP_CONCAT(t.tech_name ORDER BY pt.is_core DESC, t.tech_name SEPARATOR ', ') AS tech_stack
FROM src_projects.project p
JOIN src_projects.project_technology pt USING (project_id)
JOIN src_projects.technology t USING (tech_id)
GROUP BY p.project_id;

-- Средняя зарплата и премия по должности
SELECT r.position_title, ROUND(AVG(c.salary)/3) AS avg_monthly_salary, ROUND(AVG(c.bonus)) AS avg_quarter_bonus
FROM src_hr.resume r JOIN src_hr.compensation c USING (person_id)
GROUP BY r.position_title ORDER BY avg_monthly_salary DESC;
