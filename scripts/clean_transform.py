# -*- coding: utf-8 -*-
import pandas as pd
import hashlib
import re
import os
from datetime import datetime

# Define core project paths so the script can run from any location
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH     = os.path.join(PROJECT_ROOT, "data", "raw", "jobs_raw.csv")
CLEAN_DIR    = os.path.join(PROJECT_ROOT, "data", "clean")

# ── 1. LOAD ───────────────────────────────────────────────────────
# Load the raw scraped jobs dataset
df = pd.read_csv(RAW_PATH)
print(f"Loaded: {len(df)} rows")

# ── 2. BASIC CLEANING ─────────────────────────────────────────────
# Standardize key text columns by trimming whitespace and converting
# string "nan" values into real missing values
str_cols = ["job_title", "company", "location", "category", "job_type"]
for col in str_cols:
    df[col] = df[col].astype(str).str.strip()
    df[col] = df[col].replace("nan", None)

# Normalize date fields into consistent datetime formats
df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce").dt.strftime("%Y-%m-%d")
df["scraped_at"]  = pd.to_datetime(df["scraped_at"], errors="coerce")

# Preserve missing values as None for easier downstream database loading
df["salary_raw"]  = df["salary_raw"].where(df["salary_raw"].notna(), None)
df["tags"]        = df["tags"].where(df["tags"].notna(), None)

print("Basic cleaning done")

# ── 3. DUPLICATE DETECTION ────────────────────────────────────────
# Build a stable fingerprint from core identifying fields so duplicate
# job postings can be removed even if row order changes
def make_fingerprint(row):
    title   = str(row["job_title"]).lower().strip()
    company = str(row["company"]).lower().strip()
    loc     = str(row["location"]).lower().strip()
    url     = str(row["url"]).lower().strip()
    return hashlib.md5(f"{title}|{company}|{loc}|{url}".encode()).hexdigest()

df["fingerprint"]  = df.apply(make_fingerprint, axis=1)
df["is_duplicate"] = df.duplicated(subset="fingerprint", keep="first")

print(f"Duplicates found: {df['is_duplicate'].sum()}")

# Keep only the first occurrence of each unique job record
df = df[df["is_duplicate"] == False].drop(columns=["is_duplicate", "fingerprint"])
print(f"Rows after dedup: {len(df)}")

# ── 4. SALARY PARSING ─────────────────────────────────────────────
# Extract salary range, currency, and payment period from raw salary text
def parse_salary(raw):
    if pd.isna(raw) or not str(raw).strip():
        return None, None, None, None

    raw = str(raw).strip()

    # Infer currency symbol; default to USD when no symbol is available
    currency = "USD" if "$" in raw else "GBP" if "£" in raw else "EUR" if "€" in raw else "USD"

    # Infer whether the salary is hourly, monthly, or annual
    period   = "hourly" if "hour" in raw.lower() else "monthly" if "month" in raw.lower() else "annual"

    # Extract numeric values from salary text
    numbers  = re.findall(r"[\d,]+", raw.replace(",", ""))
    values   = []

    for n in numbers:
        try:
            val = float(n.replace(",", ""))

            # Convert shorthand values like 70k into 70000
            if val < 1000 and ("k" in raw.lower()):
                val *= 1000

            values.append(val)
        except:
            continue

    if not values:
        return None, None, currency, period

    values = sorted(set(values))

    # If only one salary value is found, treat it as both min and max
    if len(values) == 1:
        return values[0], values[0], currency, period

    return values[0], values[-1], currency, period

# Expand parsed salary output into separate structured columns
df[["min_salary", "max_salary", "currency", "salary_period"]] = df["salary_raw"].apply(
    lambda x: pd.Series(parse_salary(x))
)

print(f"Salary parsed: {df['min_salary'].notna().sum()} rows disclosed")

# ── 5. EXPERIENCE LEVEL ───────────────────────────────────────────
# Infer seniority from job title using simple keyword rules
def get_experience_level(title):
    title = str(title).lower()

    if any(w in title for w in ["junior", "entry", "graduate", "jr", "intern"]):
        return "Junior"
    elif any(w in title for w in ["senior", "lead", "principal", "sr", "head", "staff", "director", "vp"]):
        return "Senior"

    return "Mid"

df["experience_level"] = df["job_title"].apply(get_experience_level)
print(f"Experience levels:\n{df['experience_level'].value_counts().to_string()}")

# ── 6. SKILL EXTRACTION ───────────────────────────────────────────
# Map raw keywords found in tag text to standardized skill names
SKILL_MAP = {
    "python": "Python", "python3": "Python",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mysql": "MySQL", "sql server": "SQL Server",
    "sql": "SQL", "nosql": "NoSQL",
    "aws": "AWS", "gcp": "GCP", "azure": "Azure",
    "power bi": "Power BI", "powerbi": "Power BI",
    "scikit-learn": "Scikit-learn", "sklearn": "Scikit-learn",
    "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "rest api": "REST API", "restful": "REST API",
    "javascript": "JavaScript", "typescript": "TypeScript",
    "react": "React", "node.js": "Node.js", "nodejs": "Node.js",
    "ruby": "Ruby", "ruby on rails": "Ruby on Rails", "rails": "Ruby on Rails",
    "docker": "Docker", "git": "Git", "github": "GitHub",
    "tensorflow": "TensorFlow", "pytorch": "PyTorch",
    "pandas": "Pandas", "numpy": "NumPy",
    "linux": "Linux", "bash": "Bash",
    "golang": "Go", "java": "Java", "kotlin": "Kotlin",
    "swift": "Swift", "flutter": "Flutter",
    "figma": "Figma", "sketch": "Sketch",
    "salesforce": "Salesforce", "hubspot": "HubSpot",
    "jira": "Jira", "confluence": "Confluence",
    "full stack": "Full Stack", "full-stack": "Full Stack",
    "developer": "Developer", "engineer": "Engineer",
    "software engineer": "Software Engineer",
    "devops": "DevOps", "machine learning": "Machine Learning",
    "artificial intelligence": "AI",
    "data science": "Data Science", "data analyst": "Data Analyst",
    "product management": "Product Management", "product manager": "Product Management",
    "customer success": "Customer Success", "customer support": "Customer Support",
    "seo": "SEO", "design": "Design", "ux": "UX", "ui": "UI",
    "finance": "Finance", "accounting": "Accounting",
    "sales": "Sales", "business development": "Business Development",
    "marketing": "Marketing",
}

# Extract all matching skills from the tags field using whole-word matching
def extract_skills(tags_str):
    if not tags_str or pd.isna(tags_str):
        return []

    text = str(tags_str).lower()
    found = set()

    for keyword, normalised in SKILL_MAP.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', text):
            found.add(normalised)

    return list(found)

# Store extracted skills as a list for each job
df["skills"] = df["tags"].apply(extract_skills)

# Build an initial long-format list of job-skill relationships
skills_rows = []
for _, row in df.iterrows():
    for skill in row["skills"]:
        skills_rows.append({
            "job_id": row["job_id"] if "job_id" in df.columns else None,
            "skill_name": skill
        })

# ── 7. ASSIGN job_id AND SAVE ─────────────────────────────────────
# Remove the temporary skills list column before saving the main jobs table
df = df.drop(columns=["skills"]).reset_index(drop=True)

# Assign a new sequential job_id after deduplication
df["job_id"] = df.index + 1

url_to_id = dict(zip(df["url"], df["job_id"]))
skills_df = pd.DataFrame(skills_rows)

# Rebuild the skills table so each extracted skill gets the correct final job_id
skills_rows2 = []
for _, row in df.iterrows():
    for skill in extract_skills(row["tags"]):
        skills_rows2.append({
            "job_id": int(row["job_id"]),
            "skill_name": skill
        })

skills_df = pd.DataFrame(skills_rows2)

# Create output directory if needed and save cleaned datasets
os.makedirs(CLEAN_DIR, exist_ok=True)
df.to_csv(os.path.join(CLEAN_DIR, "jobs_clean.csv"), index=False)
skills_df.to_csv(os.path.join(CLEAN_DIR, "skills_clean.csv"), index=False)

# ── 8. DATA QUALITY REPORT ────────────────────────────────────────
# Print a quick summary to validate row counts and key coverage metrics
print(f"\n-- DATA QUALITY REPORT --")
print(f"Total jobs after dedup      : {len(df)}")
print(f"Salary disclosed            : {df['min_salary'].notna().mean()*100:.1f}%")
print(f"Experience level split      :\n{df['experience_level'].value_counts().to_string()}")
print(f"Total skill rows            : {len(skills_df)}")
print(f"Unique skills               : {skills_df['skill_name'].nunique()}")
print(f"Job type split              :\n{df['job_type'].value_counts().to_string()}")
print(f"\nSaved jobs_clean.csv  - {len(df)} rows")
print(f"Saved skills_clean.csv - {len(skills_df)} rows")