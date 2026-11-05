
import requests
import json
import csv
import os

from config import CRM_API_BASE, CRM_API_TOKEN

url = f"{CRM_API_BASE}/accounts"

headers = {
    "Authorization": f"Bearer {CRM_API_TOKEN}",
    "Accept": "application/json"
}

all_accounts = []
page = 1
page_size = 50

while True:
    print(f"Retrieving page {page}...")

    response = requests.get(
        url,
        headers=headers,
        params={
            "page": page,
            "page_size": page_size
        },
        timeout=30
    )

    response.raise_for_status()

    result = response.json()

    accounts = result["data"]
    total = result["total"]

    all_accounts.extend(accounts)

    print(f"Retrieved {len(accounts)} accounts")

    if len(all_accounts) >= total or not accounts:
        break

    page += 1

# Create data folder if it does not exist
os.makedirs("data", exist_ok=True)

# Save all accounts as JSON
with open("data/crm_accounts.json", "w", encoding="utf-8") as file:
    json.dump(all_accounts, file, indent=2)

# Save all accounts as CSV
if all_accounts:
    with open(
        "data/crm_accounts.csv",
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=all_accounts[0].keys()
        )
        writer.writeheader()
        writer.writerows(all_accounts)

print("\n-----------------------------")
print("CRM DOWNLOAD COMPLETE")
print("-----------------------------")
print("Total accounts:", len(all_accounts))
print("JSON saved: data/crm_accounts.json")
print("CSV saved: data/crm_accounts.csv")
