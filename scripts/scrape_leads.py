import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_sheet():
    sa_json = os.environ.get("GCP_SA_KEY")
    sheet_id = os.environ.get("SPREADSHEET_ID")
    if not sa_json or not sheet_id:
        raise ValueError("GCP_SA_KEY ya SPREADSHEET_ID missing hai.")

    creds_dict = json.loads(sa_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).sheet1

def scrape_leads():
    leads = []
    reddit_queries = [
        '"Bland AI" expensive',
        '"Vapi" alternative',
        '"AI receptionist" cost',
        '"AI phone agent" agency',
        '"voice agent" self hosted'
    ]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for q in reddit_queries:
        url = f"https://www.reddit.com/search.json?q={requests.utils.quote(q)}&sort=new&limit=15"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                for post in data.get("data", {}).get("children", []):
                    p = post.get("data", {})
                    if p.get("stickied") or p.get("over_18"):
                        continue
                    leads.append([
                        "Reddit",
                        p.get("author", "N/A"),
                        p.get("title", ""),
                        f"https://reddit.com{p.get('permalink', '')}",
                        p.get("selftext", "")[:300].replace("\n", " ")
                    ])
        except Exception as e:
            print(f"Error fetching query {q}: {e}")

    return leads

def main():
    print("Scraping started...")
    leads = scrape_leads()
    print(f"Found {len(leads)} posts.")

    if not leads:
        print("Koi lead nahi mili.")
        return

    sheet = get_sheet()
    existing_records = sheet.get_all_values()

    if not existing_records:
        sheet.append_row(["Platform", "Username", "Title", "URL", "Snippet"])
        existing_urls = set()
    else:
        existing_urls = set(row[3] for row in existing_records[1:] if len(row) > 3)

    unique_rows = [row for row in leads if row[3] not in existing_urls]

    if unique_rows:
        sheet.append_rows(unique_rows)
        print(f"{len(unique_rows)} fresh leads Google Sheet mein add ho gayi.")
    else:
        print("Saari leads already Sheet mein hain.")

if __name__ == "__main__":
    main()
