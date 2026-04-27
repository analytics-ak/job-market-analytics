CREATE DATABASE IF NOT EXISTS job_market_db;
USE job_market_db;

CREATE TABLE IF NOT EXISTS dim_company (
    company_id   INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_location (
    location_id INT AUTO_INCREMENT PRIMARY KEY,
    city        VARCHAR(255),
    country     VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS dim_skill (
    skill_id   INT AUTO_INCREMENT PRIMARY KEY,
    skill_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS fact_jobs (
    job_id           INT AUTO_INCREMENT PRIMARY KEY,
    job_title        VARCHAR(255) NOT NULL,
    experience_level VARCHAR(50),
    date_posted      DATE,
    scraped_at       DATETIME,
    url              VARCHAR(500),
    tags             TEXT,
    salary_raw       VARCHAR(255),
    min_salary       DECIMAL(12,2),
    max_salary       DECIMAL(12,2),
    currency         VARCHAR(10),
    salary_period    VARCHAR(20),
    job_type         VARCHAR(50),
    category         VARCHAR(100),
    company_id       INT,
    location_id      INT,
    FOREIGN KEY (company_id)  REFERENCES dim_company(company_id),
    FOREIGN KEY (location_id) REFERENCES dim_location(location_id)
);

CREATE TABLE IF NOT EXISTS bridge_job_skills (
    job_id   INT NOT NULL,
    skill_id INT NOT NULL,
    PRIMARY KEY (job_id, skill_id),
    FOREIGN KEY (job_id)   REFERENCES fact_jobs(job_id),
    FOREIGN KEY (skill_id) REFERENCES dim_skill(skill_id)
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    run_id                   INT AUTO_INCREMENT PRIMARY KEY,
    run_started_at           DATETIME NOT NULL,
    run_finished_at          DATETIME,
    source_name              VARCHAR(100),
    total_records_scraped    INT DEFAULT 0,
    total_duplicates_removed INT DEFAULT 0,
    total_loaded             INT DEFAULT 0
);