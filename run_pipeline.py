# -*- coding: utf-8 -*-
import subprocess
import sys
import os
import re
from datetime import datetime
from sqlalchemy import create_engine, text

BASE        = os.path.dirname(os.path.abspath(__file__))
DB_USER     = "root"
DB_PASSWORD = "zoom_123"
DB_HOST     = "localhost"
DB_NAME     = "job_market_db"

PYTHON = r"C:\Users\ashis\anaconda3\python.exe"

def run_script(script_name):
    path = os.path.join(BASE, "scripts", script_name)
    print(f"\nRunning: {script_name}")
    result = subprocess.run([PYTHON, path], capture_output=True, text=True, cwd=BASE)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        print(f"FAILED: {script_name}")
        sys.exit(1)
    return result.stdout

started_at = datetime.now()
print(f"Pipeline started: {started_at}")

scrape_out = run_script("scrape_jobs.py")
clean_out  = run_script("clean_transform.py")
load_out   = run_script("load_to_mysql.py")

finished_at = datetime.now()
print(f"Pipeline finished: {finished_at}")

def extract_number(text, keyword):
    match = re.search(rf"{keyword}[:\s]+(\d+)", text, re.IGNORECASE)
    return int(match.group(1)) if match else 0

total_scraped = extract_number(scrape_out, "Total scraped")
total_dupes   = extract_number(clean_out,  "Duplicates found")
total_loaded  = extract_number(load_out,   "fact_jobs")

engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}")

with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO scrape_runs (
            run_started_at, run_finished_at, source_name,
            total_records_scraped, total_duplicates_removed, total_loaded
        ) VALUES (:started, :finished, :source, :scraped, :dupes, :loaded)
    """), {
        "started":  started_at,
        "finished": finished_at,
        "source":   "nodesk.co",
        "scraped":  total_scraped,
        "dupes":    total_dupes,
        "loaded":   total_loaded,
    })

with engine.connect() as conn:
    row = conn.execute(text("SELECT * FROM scrape_runs ORDER BY run_id DESC LIMIT 1")).fetchone()
    print(f"\n-- SCRAPE RUN AUDIT --")
    print(f"  run_id          : {row[0]}")
    print(f"  started         : {row[1]}")
    print(f"  finished        : {row[2]}")
    print(f"  source          : {row[3]}")
    print(f"  total_scraped   : {row[4]}")
    print(f"  dupes_removed   : {row[5]}")
    print(f"  total_loaded    : {row[6]}")

print("\nPipeline complete.")