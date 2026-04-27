# -*- coding: utf-8 -*-
# Import required libraries
import requests                      # For sending HTTP requests to web pages
from bs4 import BeautifulSoup        # For parsing HTML content
import pandas as pd                  # For data manipulation and saving to CSV
from datetime import datetime        # For timestamping scraped data
import time                          # To add delays between requests (avoid blocking)
import os                            # For handling file paths

# HTTP headers to mimic a real browser request (helps avoid being blocked)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,...",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

# Base URL of the website
BASE_URL = "https://nodesk.co"

# List of job category endpoints to scrape
CATEGORY_URLS = [
    "/remote-jobs/engineering/",
    "/remote-jobs/customer-support/",
    "/remote-jobs/design/",
    "/remote-jobs/marketing/",
    "/remote-jobs/non-tech/",
    "/remote-jobs/operations/",
    "/remote-jobs/product/",
    "/remote-jobs/sales/",
    "/remote-jobs/other/",
]

# Get project root directory (two levels up from current file)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scrape_page(url):
    """
    Scrapes a single page of job listings.

    Args:
        url (str): URL of the page to scrape

    Returns:
        jobs (list): List of extracted job dictionaries
        next_page (str or None): URL of next page (if pagination exists)
    """
    # Send GET request to the page
    response = requests.get(url, headers=HEADERS, timeout=10)

    # Handle failed request
    if response.status_code != 200:
        print(f"  Failed: {url} - status {response.status_code}")
        return [], None

    # Parse HTML content
    soup = BeautifulSoup(response.text, "html.parser")

    # Find all list items and filter valid job cards
    all_li = soup.find_all("li")
    cards = [li for li in all_li if li.find("h2") and li.find("h3")]

    jobs = []

    # Loop through each job card and extract details
    for card in cards:
        try:
            # --- Job Title & URL ---
            h2 = card.find("h2")
            link_tag = h2.find("a") if h2 else None

            if not link_tag:
                continue

            job_title = link_tag.text.strip()

            # Handle relative vs absolute URLs
            job_url = BASE_URL + link_tag["href"] if link_tag["href"].startswith("/") else link_tag["href"]

            # --- Company Name ---
            h3 = card.find("h3")
            company_link = h3.find("a") if h3 else None
            company = company_link.text.strip() if company_link else (h3.text.strip() if h3 else None)

            # --- Location ---
            h5_tags = card.find_all("h5")
            location = ", ".join([h.text.strip() for h in h5_tags if h.text.strip()]) or None

            # --- Job Metadata (Category, Type, Salary) ---
            h4_tags = card.find_all("h4")
            category = None
            job_type = None
            salary_raw = None

            for h4 in h4_tags:
                text = h4.text.strip()
                text_lower = text.lower()

                # Identify salary based on currency or numeric patterns
                if any(x in text for x in ["$", "£", "€"]) or ("k" in text_lower and any(c.isdigit() for c in text)):
                    salary_raw = text

                # Identify job type
                elif any(x in text_lower for x in ["full-time", "part-time", "contract", "freelance"]):
                    job_type = text

                # Otherwise treat as category (excluding "Remote:")
                elif text and text != "Remote:":
                    category = text

            # --- Tags (skills/keywords) ---
            tags = []
            tag_ul = card.find("ul", class_="list")

            if tag_ul:
                tags = [a.text.strip() for a in tag_ul.find_all("a") if a.text.strip()]

            # --- Append structured job data ---
            jobs.append({
                "job_title": job_title,
                "company": company,
                "location": location,
                "category": category,
                "job_type": job_type,
                "salary_raw": salary_raw,
                "tags": ", ".join(tags) if tags else None,
                "date_posted": datetime.today().strftime("%Y-%m-%d"),
                "url": job_url,
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

        except Exception as e:
            # Catch errors per card to avoid breaking entire scraping
            print(f"  Card error: {e}")
            continue

    # --- Pagination: Find next page ---
    next_page = None
    next_tag = soup.find("a", string=lambda t: t and "next" in t.lower())

    if next_tag and next_tag.get("href"):
        next_page = BASE_URL + next_tag["href"]

    return jobs, next_page


def scrape_category(category_path, max_pages=5):
    """
    Scrapes multiple pages within a job category.

    Args:
        category_path (str): Category URL path
        max_pages (int): Limit to avoid infinite scraping

    Returns:
        list: All jobs scraped from the category
    """
    url = BASE_URL + category_path
    all_jobs = []
    page_num = 1

    # Loop through paginated pages
    while url and page_num <= max_pages:
        print(f"  Page {page_num}: {url}")

        jobs, next_url = scrape_page(url)

        print(f"    Got {len(jobs)} jobs")

        all_jobs.extend(jobs)

        # Move to next page
        url = next_url
        page_num += 1

        # Sleep to prevent rate limiting / blocking
        time.sleep(2)

    return all_jobs


def main():
    """
    Main execution function:
    - Iterates through all categories
    - Collects job data
    - Saves results to CSV
    """
    all_jobs = []

    # Loop through each category
    for cat in CATEGORY_URLS:
        print(f"Scraping: {cat}")

        jobs = scrape_category(cat)

        print(f"  Category total: {len(jobs)}")

        all_jobs.extend(jobs)

    print(f"Total scraped: {len(all_jobs)}")

    # --- Save data to CSV ---
    output_path = os.path.join(PROJECT_ROOT, "data", "raw", "jobs_raw.csv")

    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    df = pd.DataFrame(all_jobs)

    df.to_csv(output_path, index=False)

    print(f"Saved {len(df)} rows to {output_path}")


# Entry point check (ensures script runs only when executed directly)
if __name__ == "__main__":
    main()