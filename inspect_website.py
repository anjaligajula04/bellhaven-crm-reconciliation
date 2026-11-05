
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://analyst-assessment-production.up.railway.app"

response = requests.get(BASE_URL, timeout=30)
print("Website status:", response.status_code)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

# Print website title
print("\nWEBSITE TITLE:")
print(soup.title.get_text(strip=True) if soup.title else "No title found")

# Print all links
print("\nWEBSITE LINKS:")

for link in soup.find_all("a", href=True):
    name = link.get_text(" ", strip=True)
    href = urljoin(BASE_URL, link["href"])

    if name or href:
        print(f"Text: {name} | URL: {href}")

# Print visible page text
print("\nPAGE TEXT PREVIEW:")
print(soup.get_text(" ", strip=True)[:5000])
