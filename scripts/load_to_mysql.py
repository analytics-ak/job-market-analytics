# -*- coding: utf-8 -*-
# Import libraries for data handling, database connection, and file operations
import pandas as pd
from sqlalchemy import create_engine, text
import os

# Resolve the project root so file paths work regardless of where the script is run
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN_DIR    = os.path.join(PROJECT_ROOT, "data", "clean")

# Database connection settings for the local MySQL job market database
DB_USER     = "root"
DB_PASSWORD = "Your_Password"
DB_HOST     = "localhost"
DB_NAME     = "job_market_db"

# Create a SQLAlchemy engine for executing inserts and queries
engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}")

# Load cleaned job and skill datasets from the data folder
jobs   = pd.read_csv(os.path.join(CLEAN_DIR, "jobs_clean.csv"))
skills = pd.read_csv(os.path.join(CLEAN_DIR, "skills_clean.csv"))

# Replace missing values with None so MySQL can store them as NULL
jobs["currency"]      = jobs["currency"].where(jobs["currency"].notna(), None)
jobs["salary_period"] = jobs["salary_period"].where(jobs["salary_period"].notna(), None)
jobs["tags"]          = jobs["tags"].where(jobs["tags"].notna(), None)
jobs["salary_raw"]    = jobs["salary_raw"].where(jobs["salary_raw"].notna(), None)

# Ensure salary columns are numeric before loading into the database
jobs["min_salary"]    = pd.to_numeric(jobs["min_salary"], errors="coerce")
jobs["max_salary"]    = pd.to_numeric(jobs["max_salary"], errors="coerce")

# Show how many records will be loaded from each dataset
print(f"Jobs to load   : {len(jobs)}")
print(f"Skills to load : {len(skills)}")

# Helper function to convert NaN or invalid values into None
# This avoids database insert errors caused by pandas missing-value types
def safe(val):
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except:
        pass
    return val

# Insert unique companies into the company dimension table
companies = jobs[["company"]].drop_duplicates().dropna()
companies.columns = ["company_name"]
with engine.begin() as conn:
    for _, row in companies.iterrows():
        conn.execute(
            text("INSERT IGNORE INTO dim_company (company_name) VALUES (:name)"),
            {"name": row["company_name"]}
        )

# Confirm how many company records were loaded
with engine.connect() as conn:
    print(f"dim_company    : {conn.execute(text('SELECT COUNT(*) FROM dim_company')).scalar()} rows")

# Insert unique locations into the location dimension table
locations = jobs[["location"]].drop_duplicates().dropna()
with engine.begin() as conn:
    for _, row in locations.iterrows():
        conn.execute(
            text("INSERT IGNORE INTO dim_location (city) VALUES (:city)"),
            {"city": row["location"]}
        )

# Confirm how many location records were loaded
with engine.connect() as conn:
    print(f"dim_location   : {conn.execute(text('SELECT COUNT(*) FROM dim_location')).scalar()} rows")

# Insert unique skills into the skill dimension table
skill_names = skills[["skill_name"]].drop_duplicates().dropna()
with engine.begin() as conn:
    for _, row in skill_names.iterrows():
        conn.execute(
            text("INSERT IGNORE INTO dim_skill (skill_name) VALUES (:name)"),
            {"name": row["skill_name"]}
        )

# Confirm how many skill records were loaded
with engine.connect() as conn:
    print(f"dim_skill      : {conn.execute(text('SELECT COUNT(*) FROM dim_skill')).scalar()} rows")

# Build lookup maps so foreign keys can be assigned in the fact table
with engine.connect() as conn:
    company_map  = {r[0]: r[1] for r in conn.execute(text("SELECT company_name, company_id FROM dim_company"))}
    location_map = {r[0]: r[1] for r in conn.execute(text("SELECT city, location_id FROM dim_location"))}

# Load the job records into the fact table with foreign key references
with engine.begin() as conn:
    for _, row in jobs.iterrows():
        conn.execute(text("""
            INSERT IGNORE INTO fact_jobs (
                job_id, job_title, experience_level, date_posted, scraped_at,
                url, tags, salary_raw, min_salary, max_salary,
                currency, salary_period, job_type, category,
                company_id, location_id
            ) VALUES (
                :job_id, :job_title, :experience_level, :date_posted, :scraped_at,
                :url, :tags, :salary_raw, :min_salary, :max_salary,
                :currency, :salary_period, :job_type, :category,
                :company_id, :location_id
            )
        """), {
            "job_id":           int(row["job_id"]),
            "job_title":        safe(row["job_title"]),
            "experience_level":  safe(row["experience_level"]),
            "date_posted":      safe(row["date_posted"]),
            "scraped_at":       safe(row["scraped_at"]),
            "url":              safe(row["url"]),
            "tags":             safe(row["tags"]),
            "salary_raw":       safe(row["salary_raw"]),
            "min_salary":       None if pd.isna(row["min_salary"]) else float(row["min_salary"]),
            "max_salary":       None if pd.isna(row["max_salary"]) else float(row["max_salary"]),
            "currency":         safe(row["currency"]),
            "salary_period":    safe(row["salary_period"]),
            "job_type":         safe(row["job_type"]),
            "category":         safe(row["category"]),
            "company_id":       company_map.get(row["company"]),
            "location_id":      location_map.get(row["location"]),
        })

# Confirm how many fact rows were loaded
with engine.connect() as conn:
    print(f"fact_jobs      : {conn.execute(text('SELECT COUNT(*) FROM fact_jobs')).scalar()} rows")

# Prepare the bridge table data by ensuring skill rows have valid job IDs and skill names
skills["job_id"]     = pd.to_numeric(skills["job_id"], errors="coerce")
skills["skill_name"] = skills["skill_name"].where(skills["skill_name"].notna(), None)
skills = skills.dropna(subset=["job_id", "skill_name"])

# Build a lookup map for translating skill names into skill IDs
with engine.connect() as conn:
    skill_map = {r[0]: r[1] for r in conn.execute(text("SELECT skill_name, skill_id FROM dim_skill"))}

# Load many-to-many job-skill relationships into the bridge table
with engine.begin() as conn:
    for _, row in skills.iterrows():
        skill_id = skill_map.get(row["skill_name"])
        if not skill_id:
            continue
        try:
            conn.execute(text("""
                INSERT IGNORE INTO bridge_job_skills (job_id, skill_id)
                VALUES (:job_id, :skill_id)
            """), {"job_id": int(row["job_id"]), "skill_id": skill_id})
        except Exception:
            continue

# Confirm how many bridge records were loaded
with engine.connect() as conn:
    print(f"bridge_skills  : {conn.execute(text('SELECT COUNT(*) FROM bridge_job_skills')).scalar()} rows")

# Run a final row-count check to verify that each table loaded correctly
print("\n-- LOAD VERIFICATION --")
with engine.connect() as conn:
    for table in ["dim_company", "dim_location", "dim_skill", "fact_jobs", "bridge_job_skills"]:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        print(f"  {table}: {count} rows")