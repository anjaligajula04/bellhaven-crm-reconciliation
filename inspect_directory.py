
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://analyst-assessment-production.up.railway.app"

for page in [1, 2, 3]:
    url = f"{BASE_URL}/communities?page={page}"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    print("\n" + "=" * 60)
    print(f"DIRECTORY PAGE {page}")
    print("=" * 60)

    print(soup.get_text(" ", strip=True)[:6000])

    print("\nCOMMUNITY LINKS:")

    for link in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, link["href"])

        if "/communities/" in href and href != f"{BASE_URL}/communities":
            print(link.get_text(" ", strip=True), "->", href)

# Inspect one individual community page
detail_url = f"{BASE_URL}/communities/bellhaven-of-maplewood"

response = requests.get(detail_url, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

print("\n" + "=" * 60)
print("INDIVIDUAL COMMUNITY PAGE")
print("=" * 60)

print(soup.get_text(" ", strip=True)[:6000])
