
import requests
import json
import csv
import os
import re
import time

from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://analyst-assessment-production.up.railway.app"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 BellhavenReconciliation/1.0"
})


def get_soup(url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def get_section(text, start_label, end_label):
    pattern = (
        re.escape(start_label)
        + r"\s*(.*?)\s*"
        + re.escape(end_label)
    )

    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()

    return ""


def collect_community_links():
    links = {}

    page = 1

    while True:
        url = f"{BASE_URL}/communities?page={page}"

        print(f"Reading directory page {page}...")

        soup = get_soup(url)

        for link in soup.find_all("a", href=True):
            href = urljoin(BASE_URL, link["href"])
            name = link.get_text(" ", strip=True)

            if (
                "/communities/" in href
                and href != f"{BASE_URL}/communities"
                and name
            ):
                links[href] = name

        next_link = soup.find(
            "a",
            string=re.compile(r"Next", re.IGNORECASE)
        )

        if not next_link:
            break

        page += 1

    return links


def scrape_community(url, directory_name):
    soup = get_soup(url)

    text = soup.get_text(" ", strip=True)

    # Get the official community heading
    heading = soup.find("h1")

    if heading:
        name = heading.get_text(" ", strip=True)
    else:
        name = directory_name

    # Extract sections from the individual facility page
    address = get_section(text, "Address", "Care Offerings")

    care = get_section(
        text,
        "Care Offerings",
        "Administrator"
    )

    administrator = get_section(
        text,
        "Administrator",
        "Phone"
    )

    phone = get_section(
        text,
        "Phone",
        "Back to all communities"
    )

    # Parse city, state and ZIP from the address
    city = ""
    state = ""
    zip_code = ""
    street = ""

    address_match = re.search(
        r"^(.*?)\s+([^,]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$",
        address
    )

    if address_match:
        street = address_match.group(1).strip()
        city = address_match.group(2).strip()
        state = address_match.group(3).strip()
        zip_code = address_match.group(4).strip()

    else:
        print(f"WARNING: Could not parse address for {name}: {address}")

    return {
        "name": name,
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "full_address": address,
        "care_type": care,
        "administrator": administrator,
        "phone": phone,
        "source_url": url
    }


def main():

    print("\nStarting Bellhaven website scraper...\n")

    # Collect all directory community URLs
    community_links = collect_community_links()

    print("\nDirectory communities found:", len(community_links))

    # Check homepage for separately announced communities
    homepage = get_soup(BASE_URL)

    for link in homepage.find_all("a", href=True):
        href = urljoin(BASE_URL, link["href"])
        name = link.get_text(" ", strip=True)

        if (
            "/communities/" in href
            and href != f"{BASE_URL}/communities"
            and href not in community_links
        ):
            community_links[href] = name
            print("Additional homepage community found:", name)

    print("\nTotal unique community pages:", len(community_links))

    results = []

    for index, (url, directory_name) in enumerate(
        community_links.items(),
        start=1
    ):
        print(
            f"Scraping {index}/{len(community_links)}: "
            f"{directory_name}"
        )

        try:
            record = scrape_community(url, directory_name)
            results.append(record)

        except requests.RequestException as error:
            print(f"ERROR scraping {url}: {error}")

        except Exception as error:
            print(f"UNEXPECTED ERROR for {directory_name}: {error}")

        time.sleep(0.2)

    # Save output files
    os.makedirs("data", exist_ok=True)

    json_path = "data/website_communities.json"
    csv_path = "data/website_communities.csv"

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)

    if results:
        with open(
            csv_path,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=results[0].keys()
            )

            writer.writeheader()
            writer.writerows(results)

    print("\n" + "=" * 50)
    print("WEBSITE SCRAPING COMPLETE")
    print("=" * 50)

    print("Directory URLs discovered:", len(community_links))
    print("Successfully scraped:", len(results))
    print("JSON file:", json_path)
    print("CSV file:", csv_path)

    # Report incomplete records
    incomplete = [
        record["name"]
        for record in results
        if not record["street"]
        or not record["city"]
        or not record["state"]
        or not record["zip"]
    ]

    print("\nRecords with incomplete addresses:", len(incomplete))

    for name in incomplete:
        print("-", name)


if __name__ == "__main__":
    main()
