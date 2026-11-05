import json
import re
from pathlib import Path
from collections import defaultdict
from rapidfuzz import fuzz


# --------------------------------------------------
# FILE LOCATIONS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

WEBSITE_FILE = BASE_DIR / "data" / "website_communities.json"
CRM_FILE = BASE_DIR / "data" / "crm_accounts.json"
REPORT_DIR = BASE_DIR / "reports"

MATCHING_FILE = REPORT_DIR / "matching_results.json"
CSV_FILE = REPORT_DIR / "matching_results.csv"
UNSELECTED_FILE = REPORT_DIR / "unselected_crm_accounts.json"
DUPLICATES_FILE = REPORT_DIR / "crm_duplicate_candidates.json"
DECISIONS_FILE = REPORT_DIR / "review_decisions.json"


# --------------------------------------------------
# NORMALIZATION HELPERS
# --------------------------------------------------

def clean(value):
    return str(value or "").strip()


def normalize_text(value):
    value = clean(value).lower()
    value = re.sub(r"[^a-z0-9 ]", " ", value)

    replacements = {
        " street ": " st ",
        " avenue ": " ave ",
        " road ": " rd ",
        " drive ": " dr ",
        " boulevard ": " blvd ",
        " lane ": " ln ",
        " court ": " ct ",
        " parkway ": " pkwy ",
        " circle ": " cir ",
        " place ": " pl ",
        " highway ": " hwy ",
        " north ": " n ",
        " south ": " s ",
        " east ": " e ",
        " west ": " w ",
        " pike ": " pike ",
    }

    value = f" {value} "

    for old, new in replacements.items():
        value = value.replace(old, new)

    return " ".join(value.split())


def digits(value):
    return re.sub(r"\D", "", clean(value))


def similarity(first, second):
    first = normalize_text(first)
    second = normalize_text(second)

    if not first or not second:
        return 0.0

    return float(fuzz.token_set_ratio(first, second))


# --------------------------------------------------
# WEBSITE ADDRESS PARSING
# --------------------------------------------------

STREET_ENDINGS = (
    r"street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd|"
    r"lane|ln|court|ct|parkway|pkwy|circle|cir|place|pl|"
    r"highway|hwy|pike|terrace|ter|way|broadway"
)

def parse_website_address(address):
    """
    Parse addresses such as:
    210 Orchard Lane Maplewood, OH 44280
    1120 W Main St Owosso, MI 48867
    """

    address = clean(address)

    result = {
        "street": "",
        "city": "",
        "state": "",
        "zip": "",
    }

    state_zip = re.search(
        r",?\s*([A-Z]{2})\s+(\d{5})(?:-\d{4})?$",
        address,
        re.IGNORECASE,
    )

    if not state_zip:
        return result

    result["state"] = state_zip.group(1).upper()
    result["zip"] = state_zip.group(2)

    before_state = address[:state_zip.start()].strip().rstrip(",")

    # Find the street ending so that the remaining text is the city.
    pattern = (
        r"^(.+?\b(?:" + STREET_ENDINGS + r")\.?)\s+(.+)$"
    )

    street_city = re.match(pattern, before_state, re.IGNORECASE)

    if street_city:
        result["street"] = street_city.group(1).strip()
        result["city"] = street_city.group(2).strip()
    else:
        result["street"] = before_state

    return result


# --------------------------------------------------
# LOAD INPUT FILES
# --------------------------------------------------

def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with open(path, "r", encoding="utf-8-sig") as file:
        return json.load(file)


website_records = load_json(WEBSITE_FILE)
crm_records = load_json(CRM_FILE)

if isinstance(website_records, dict):
    website_records = website_records.get("data", [])

if isinstance(crm_records, dict):
    crm_records = crm_records.get("data", [])

print(f"Website communities loaded: {len(website_records)}")
print(f"CRM accounts loaded: {len(crm_records)}")


# --------------------------------------------------
# IDENTIFY CRM PARENT ACCOUNT
# --------------------------------------------------

bellhaven_parent_id = "0015QAPLGS3FVYEEEM"

for account in crm_records:
    account_name = normalize_text(account.get("name"))

    if account_name == "bellhaven senior living":
        bellhaven_parent_id = account.get("account_id")
        break


# --------------------------------------------------
# PREPARE CRM FACILITY ACCOUNTS
# Exclude parent organizations without facility addresses.
# --------------------------------------------------

facility_accounts = []

for account in crm_records:
    street = clean(account.get("billing_street"))
    city = clean(account.get("billing_city"))
    state = clean(account.get("billing_state"))
    postal = clean(account.get("billing_zip"))

    name = clean(account.get("name"))

    if not name or not street or not city:
        continue

    if "parent account" in name.lower():
        continue

    facility_accounts.append(account)

print(f"CRM facility accounts available for matching: {len(facility_accounts)}")


# --------------------------------------------------
# MATCHING FUNCTION
# --------------------------------------------------

def score_candidate(website, account):

    website_name = clean(website.get("name"))
    website_address = clean(website.get("full_address"))

    parsed = parse_website_address(website_address)

    crm_name = clean(account.get("name"))
    crm_street = clean(account.get("billing_street"))
    crm_city = clean(account.get("billing_city"))
    crm_state = clean(account.get("billing_state"))
    crm_zip = clean(account.get("billing_zip"))

    name_score = similarity(website_name, crm_name)
    street_score = similarity(parsed["street"], crm_street)
    city_score = similarity(parsed["city"], crm_city)

    state_score = (
        100.0
        if parsed["state"] and parsed["state"] == crm_state.upper()
        else 0.0
    )

    zip_score = (
        100.0
        if parsed["zip"] and parsed["zip"] == crm_zip[:5]
        else 0.0
    )

    match_score = (
        name_score * 0.60
        + street_score * 0.15
        + city_score * 0.10
        + state_score * 0.05
        + zip_score * 0.10
    )

        # A physical location match requires matching city, state,
    # and street address. ZIP alone is not sufficient.
    location_match = (
        city_score >= 85
        and state_score == 100
        and street_score >= 80
    )

    conflicts = []

    if parsed["state"] and state_score == 0:
        conflicts.append("State mismatch")

    if parsed["zip"] and zip_score == 0:
        conflicts.append("ZIP code mismatch")

    if parsed["city"] and city_score < 70:
        conflicts.append("City mismatch")

    if parsed["street"] and street_score < 60:
        conflicts.append("Street mismatch")

    return {
        "account": account,
        "match_score": round(match_score, 2),
        "name_score": round(name_score, 2),
        "street_score": round(street_score, 2),
        "city_score": round(city_score, 2),
        "state_score": round(state_score, 2),
        "zip_score": round(zip_score, 2),
        "location_match": location_match,
        "address_conflicts": conflicts,
    }


# --------------------------------------------------
# GENERATE MATCHING RESULTS
# --------------------------------------------------

results = []

for website in website_records:

    website_name = clean(website.get("name"))
    website_address = clean(website.get("full_address"))
    website_phone = clean(website.get("phone"))
    website_url = clean(website.get("source_url"))

    candidates = [
        score_candidate(website, account)
        for account in facility_accounts
    ]

        # Separate physically matching accounts from name-only candidates.
    location_candidates = [
        item for item in candidates
        if item["location_match"]
    ]

    location_candidates.sort(
        key=lambda item: (
            item["match_score"],
            item["name_score"],
        ),
        reverse=True,
    )

    # Only a physical-location candidate can become the primary match.
    best = location_candidates[0] if location_candidates else None

    # Keep the second location candidate for ambiguity review.
    second = location_candidates[1] if len(location_candidates) > 1 else None

    # Retain the best name-only candidate as evidence when no
    # physical-location match exists.
    name_only_candidate = None

    if not best and candidates:
        name_only_candidate = max(
            candidates,
            key=lambda item: (
                item["name_score"],
                item["match_score"],
            ),
        )
            # Preserve the strongest name-only candidate for manual review.
    name_only_candidate_name = ""
    name_only_candidate_id = ""
    name_only_candidate_address = ""
    name_only_candidate_name_score = 0
    name_only_candidate_match_score = 0

    if name_only_candidate:
        name_only_account = name_only_candidate["account"]

        name_only_candidate_name = clean(
            name_only_account.get("name")
        )

        name_only_candidate_id = clean(
            name_only_account.get("account_id")
        )

        name_only_candidate_address = (
            f"{clean(name_only_account.get('billing_street'))}, "
            f"{clean(name_only_account.get('billing_city'))}, "
            f"{clean(name_only_account.get('billing_state'))} "
            f"{clean(name_only_account.get('billing_zip'))}"
        )

        name_only_candidate_name_score = (
            name_only_candidate["name_score"]
        )

        name_only_candidate_match_score = (
            name_only_candidate["match_score"]
        )


    if best:
        account = best["account"]

        crm_id = clean(account.get("account_id"))
        crm_name = clean(account.get("name"))
        crm_street = clean(account.get("billing_street"))
        crm_city = clean(account.get("billing_city"))
        crm_state = clean(account.get("billing_state"))
        crm_zip = clean(account.get("billing_zip"))

        crm_address = (
            f"{crm_street}, {crm_city}, {crm_state} {crm_zip}"
        )

        crm_phone = clean(account.get("phone"))
        parent_id = clean(account.get("parent_id"))
        parent_name = clean(account.get("parent_name"))

        revenue = float(account.get("lifetime_revenue") or 0)
        outstanding_ar = float(account.get("outstanding_ar") or 0)

        match_score = best["match_score"]
        name_score = best["name_score"]
        street_score = best["street_score"]
        city_score = best["city_score"]
        state_score = best["state_score"]
        zip_score = best["zip_score"]
        location_match = best["location_match"]
        conflicts = best["address_conflicts"]

        second_candidate = (
            clean(second["account"].get("name"))
            if second else ""
        )

        second_candidate_id = (
            clean(second["account"].get("account_id"))
            if second else ""
        )

        second_candidate_score = (
            second["match_score"] if second else 0
        )

    else:
        crm_id = ""
        crm_name = ""
        crm_address = ""
        crm_phone = ""
        parent_id = ""
        parent_name = ""

        revenue = 0
        outstanding_ar = 0

        match_score = 0
        name_score = 0
        street_score = 0
        city_score = 0
        state_score = 0
        zip_score = 0

        location_match = False
        conflicts = ["No CRM facility candidates available"]

        second_candidate = ""
        second_candidate_id = ""
        second_candidate_score = 0

    # --------------------------------------------------
        # Detect multiple CRM accounts at the same physical location.
    location_candidate_count = len(location_candidates)

    multiple_location_candidates = location_candidate_count > 1

        # REVIEW CATEGORY

    if multiple_location_candidates:
        review_status = "MANUAL REVIEW"

    elif (
        not best
        and name_only_candidate
        and name_only_candidate["name_score"] >= 60
    ):
        review_status = "MANUAL REVIEW"

    elif not best:
        review_status = "POSSIBLY MISSING FROM CRM"

    elif (
        match_score >= 90
        and name_score >= 80
        and location_match
        and not conflicts
    ):
        review_status = "LIKELY MATCH - VERIFY"

    else:
        review_status = "MANUAL REVIEW"
    # --------------------------------------------------
    # PARENT RECOMMENDATION
    # --------------------------------------------------

    if not best:
        parent_recommendation = (
            "NO CRM ACCOUNT SELECTED - POSSIBLY MISSING; "
            "DO NOT CHANGE ANY EXISTING CRM ACCOUNT"
        )

    elif name_score < 80:
        parent_recommendation = (
            "MANUAL REVIEW - VERIFY FACILITY IDENTITY BEFORE "
            "ANY PARENT OR ACCOUNT CHANGE"
        )

    elif parent_id == bellhaven_parent_id:
        parent_recommendation = (
            "NO PARENT CHANGE NEEDED - VERIFY FACILITY IDENTITY"
        )

    elif revenue > 0 and outstanding_ar > 0:
        parent_recommendation = (
            "CREATE NEW BELLHAVEN ACCOUNT - PRESERVE OLD ACCOUNT "
            "AND FINANCIAL HISTORY; LINK OLD ACCOUNT USING "
            "CHOW_CURRENT_ACCOUNT"
        )

    elif location_match and match_score >= 75:
        parent_recommendation = (
            "REPARENT EXISTING ACCOUNT TO BELLHAVEN SENIOR LIVING "
            "- REVIEW BILLING HISTORY BEFORE APPROVAL"
        )

    else:
        parent_recommendation = (
            "MANUAL REVIEW - VERIFY ACCOUNT IDENTITY AND PARENT"
        )

    if multiple_location_candidates:
        parent_recommendation = (
            "MANUAL REVIEW - MULTIPLE CRM ACCOUNTS SHARE THIS LOCATION"
        )
    results.append({
        "website_name": website_name,
        "website_address": website_address,
        "website_phone": website_phone,
        "website_url": website_url,

        "crm_account_id": crm_id,
        "crm_name": crm_name,
        "crm_address": crm_address,
        "crm_phone": crm_phone,
        "crm_parent_id": parent_id,
        "crm_parent_name": parent_name,

        "lifetime_revenue": revenue,
        "outstanding_ar": outstanding_ar,

        "match_score": match_score,
        "name_score": name_score,
        "street_score": street_score,
        "city_score": city_score,
        "state_score": state_score,
        "zip_score": zip_score,

        "location_match": location_match,
        "address_conflicts": conflicts,
         "location_candidate_count": location_candidate_count,
        "multiple_location_candidates": multiple_location_candidates,

        "second_candidate": second_candidate,
        "second_candidate_id": second_candidate_id,
        "second_candidate_score": second_candidate_score,
                "name_only_candidate_name": name_only_candidate_name,
        "name_only_candidate_id": name_only_candidate_id,
        "name_only_candidate_address": name_only_candidate_address,
        "name_only_candidate_name_score": name_only_candidate_name_score,
        "name_only_candidate_match_score": name_only_candidate_match_score,

        "review_status": review_status,
        "parent_recommendation": parent_recommendation,

        "candidate_collision": False,
        "candidate_collision_with": "",

        "decision": "PENDING",
    })


# --------------------------------------------------
# CANDIDATE COLLISION DETECTION
# Only flag collisions when multiple website facilities
# have a physical location match to the same CRM account.
# --------------------------------------------------

account_usage = defaultdict(list)

for result in results:
    if result["crm_account_id"] and result["location_match"]:
        account_usage[result["crm_account_id"]].append(
            result["website_name"]
        )

for result in results:

    account_id = result["crm_account_id"]

    if not account_id or not result["location_match"]:
        continue

    used_by = account_usage[account_id]

    if len(used_by) > 1:

        other_names = [
            name for name in used_by
            if name != result["website_name"]
        ]

        result["candidate_collision"] = True
        result["candidate_collision_with"] = "; ".join(other_names)

        if result["review_status"] == "LIKELY MATCH - VERIFY":
            result["review_status"] = "MANUAL REVIEW"


# --------------------------------------------------
# RESTORE EXISTING LOCAL DECISIONS
# Do not overwrite the decisions file.
# --------------------------------------------------

saved_decisions = {}

if DECISIONS_FILE.exists():
    with open(DECISIONS_FILE, "r", encoding="utf-8") as file:
        saved_decisions = json.load(file)

for result in results:
    key = result.get("website_url") or result.get("website_name")

    if key in saved_decisions:
        result["decision"] = saved_decisions[key].get(
            "decision", "PENDING"
        )


# --------------------------------------------------
# UNSELECTED CRM ACCOUNTS
# --------------------------------------------------

selected_ids = {
    result["crm_account_id"]
    for result in results
    if result["crm_account_id"]
}

unselected_accounts = [
    account
    for account in crm_records
    if account.get("account_id") not in selected_ids
]


# --------------------------------------------------
# POSSIBLE DUPLICATE ADDRESS GROUPS
# --------------------------------------------------

address_groups = defaultdict(list)

for account in facility_accounts:
    address_key = normalize_text(
        " ".join([
            clean(account.get("billing_street")),
            clean(account.get("billing_city")),
            clean(account.get("billing_state")),
            clean(account.get("billing_zip")),
        ])
    )

    if address_key:
        address_groups[address_key].append(account)

duplicate_groups = []

for address, accounts in address_groups.items():

    if len(accounts) < 2:
        continue

    duplicate_groups.append({
        "normalized_address": address,
        "accounts": accounts,
    })


# --------------------------------------------------
# SAVE REPORTS
# --------------------------------------------------

REPORT_DIR.mkdir(parents=True, exist_ok=True)

with open(MATCHING_FILE, "w", encoding="utf-8") as file:
    json.dump(results, file, indent=2, ensure_ascii=False)

with open(UNSELECTED_FILE, "w", encoding="utf-8") as file:
    json.dump(unselected_accounts, file, indent=2, ensure_ascii=False)

with open(DUPLICATES_FILE, "w", encoding="utf-8") as file:
    json.dump(duplicate_groups, file, indent=2, ensure_ascii=False)

# CSV is optional; pandas is used only for this export.
import pandas as pd

pd.DataFrame(results).to_csv(CSV_FILE, index=False, encoding="utf-8-sig")


# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

print("\nBELHAVEN CRM RECONCILIATION SUMMARY")
print("=" * 45)

print(f"Website communities: {len(website_records)}")
print(f"CRM accounts: {len(crm_records)}")
print(f"Matching results: {len(results)}")

print("\nREVIEW CATEGORIES:")

for category in [
    "LIKELY MATCH - VERIFY",
    "MANUAL REVIEW",
    "POSSIBLY MISSING FROM CRM",
]:
    count = sum(
        result["review_status"] == category
        for result in results
    )
    print(f"{category}: {count}")

print("\nDECISIONS RESTORED:")

for decision in ["APPROVED", "REJECTED", "PENDING"]:
    count = sum(
        result["decision"] == decision
        for result in results
    )
    print(f"{decision}: {count}")

print(f"\nUnselected CRM accounts: {len(unselected_accounts)}")
print(f"Possible duplicate address groups: {len(duplicate_groups)}")

print("\nReports saved:")
print(MATCHING_FILE)
print(CSV_FILE)
print(UNSELECTED_FILE)
print(DUPLICATES_FILE)

print("\nNo CRM API updates were performed.")
