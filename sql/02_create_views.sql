USE job_market_db;

-- View 1: most in-demand skills across all jobs
CREATE OR REPLACE VIEW vw_top_skills AS
SELECT
    sk.skill_name,
    COUNT(DISTINCT b.job_id) AS job_count,
    ROUND(COUNT(DISTINCT b.job_id) * 100.0 / (SELECT COUNT(*) FROM fact_jobs), 2) AS pct_of_jobs
FROM bridge_job_skills b
JOIN dim_skill sk ON b.skill_id = sk.skill_id
GROUP BY sk.skill_name
ORDER BY job_count DESC;

-- View 2: job distribution by location
CREATE OR REPLACE VIEW vw_jobs_by_location AS
SELECT
    l.city,
    l.country,
    COUNT(j.job_id) AS total_jobs
FROM fact_jobs j
JOIN dim_location l ON j.location_id = l.location_id
GROUP BY l.city, l.country
ORDER BY total_jobs DESC;

-- View 3: hiring activity by company
CREATE OR REPLACE VIEW vw_jobs_by_company AS
SELECT
    c.company_name,
    COUNT(j.job_id) AS total_jobs,
    GROUP_CONCAT(DISTINCT j.experience_level) AS levels_hiring
FROM fact_jobs j
JOIN dim_company c ON j.company_id = c.company_id
GROUP BY c.company_name
ORDER BY total_jobs DESC;

-- View 4: salary analysis by experience level and currency
CREATE OR REPLACE VIEW vw_salary_by_role AS
SELECT
    experience_level,
    currency,
    COUNT(job_id)            AS jobs_with_salary,
    ROUND(AVG(min_salary), 2) AS avg_min_salary,
    ROUND(AVG(max_salary), 2) AS avg_max_salary
FROM fact_jobs
WHERE min_salary IS NOT NULL
GROUP BY experience_level, currency
ORDER BY avg_max_salary DESC;

-- Sample output from top skills view
SELECT * FROM vw_top_skills LIMIT 10;

-- Sample output from jobs by location view
SELECT * FROM vw_jobs_by_location LIMIT 5;

-- Salary summary by role
SELECT * FROM vw_salary_by_role;