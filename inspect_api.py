import requests
from config import CRM_API_BASE, CRM_API_TOKEN

account_id = "001L3LGR6W69J8DYYV"

url = f"{CRM_API_BASE}/accounts/{account_id}"

headers = {
    "Authorization": f"Bearer {CRM_API_TOKEN}"
}

response = requests.options(
    url,
    headers=headers,
    timeout=30
)

print("Status:", response.status_code)
print("Allowed methods:", response.headers.get("Allow"))
print("Response:", response.text)