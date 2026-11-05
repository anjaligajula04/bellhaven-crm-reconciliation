import json
import sys
from pathlib import Path

import requests
from config import CRM_API_BASE, CRM_API_TOKEN

BASE_DIR = Path(__file__).resolve().parent
MATCH_FILE = BASE_DIR / "reports" / "matching_results.json"
DECISION_FILE = BASE_DIR / "reports" / "review_decisions.json"
CRM_FILE = BASE_DIR / "data" / "crm_accounts.json"
REPORT_FILE = BASE_DIR / "reports" / "writeback_live_results.json"

PARENT_ID = "0015QAPLGS3FVYEEEM"

HEADERS = {
    "Authorization": f"Bearer {CRM_API_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

FACILITIES = {
    "Tiffin": {
        "name": "Bellhaven of Tiffin",
        "old_id": "001U6RW32TY0WSXZZB",
        "parent_before": "001FWSQ30SFW6S7604",
        "revenue": 84000,
        "ar": 12400,
        "address": {
            "billing_street": "45 St Lawrence Dr",
            "billing_city": "Tiffin",
            "billing_state": "OH",
            "billing_zip": "44883",
        },
        "action": "CREATE_AND_LINK",
    },
    "Marietta": {
        "name": "Bellhaven of Marietta",
        "old_id": "001A34WFSUYHCRBLFT",
        "parent_before": "001FWSQ30SFW6S7604",
        "revenue": 51250,
        "ar": 3800,
        "address": {
            "billing_street": "805 Colegate Drive",
            "billing_city": "Marietta",
            "billing_state": "OH",
            "billing_zip": "45750",
        },
        "action": "CREATE_AND_LINK",
    },
    "Lima": {
        "name": "Bellhaven Crossings of Lima",
        "old_id": "001LGFPBJY4N9MB6KL",
        "parent_before": "001FJZYHR7MLFMNPLL",
        "revenue": 47000,
        "ar": 0,
        "action": "REPARENT",
    },
    "Findlay": {
        "name": "Bellhaven Meadows of Findlay",
        "old_id": "001UKEFGADQ8YCZ4YM",
        "parent_before": "",
        "revenue": 22000,
        "ar": 0,
        "action": "REPARENT",
    },
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def api_get(path, **kwargs):
    response = requests.get(
        f"{CRM_API_BASE}{path}",
        headers=HEADERS,
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()
    return response.json()


def api_patch(account_id, payload):
    response = requests.patch(
        f"{CRM_API_BASE}/accounts/{account_id}",
        headers=HEADERS,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def api_post(payload):
    response = requests.post(
        f"{CRM_API_BASE}/accounts",
        headers=HEADERS,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_all_accounts():
    accounts = []
    page = 1

    while True:
        result = api_get(
            "/accounts",
            params={"page": page, "page_size": 50},
        )
        batch = result["data"]
        accounts.extend(batch)

        if len(accounts) >= result["total"] or not batch:
            break

        page += 1

    return accounts


def same_number(first, second):
    return float(first or 0) == float(second or 0)


def verify_original_account(account, config):
    if account["name"] != config["name"]:
        raise RuntimeError(
            f"Account name changed unexpectedly: {config['name']}"
        )

    current_parent = account.get("parent_id", "")

    if config["action"] == "REPARENT":
        if current_parent not in (config["parent_before"], PARENT_ID):
            raise RuntimeError(
                f"Unexpected current parent for {config['name']}"
            )
    elif current_parent != config["parent_before"]:
        raise RuntimeError(
            f"Unexpected current parent for {config['name']}"
        )

    if not same_number(account.get("lifetime_revenue"), config["revenue"]):
        raise RuntimeError(
            f"Revenue changed since review for {config['name']}"
        )

    if not same_number(account.get("outstanding_ar"), config["ar"]):
        raise RuntimeError(
            f"Outstanding AR changed since review for {config['name']}"
        )

    address = config.get("address", {})
    for field, expected in address.items():
        if account.get(field) != expected:
            raise RuntimeError(
                f"Address mismatch for {config['name']}: {field}"
            )


def verify_preserved(before, after, allowed_changes):
    for field in before:
        if field in allowed_changes or field == "updated_at":
            continue

        if before.get(field) != after.get(field):
            raise RuntimeError(
                f"Unexpected change to {field} on {before['account_id']}"
            )


def find_existing_new_account(accounts, config):
    candidates = []

    for account in accounts:
        if (
            account.get("created_by_candidate") is True
            and account.get("name") == config["name"]
            and account.get("parent_id") == PARENT_ID
            and all(
                account.get(field) == value
                for field, value in config["address"].items()
            )
        ):
            candidates.append(account)

    if len(candidates) > 1:
        raise RuntimeError(
            f"Multiple candidate-created accounts found for {config['name']}"
        )

    return candidates[0] if candidates else None


def main():
    execute = "--execute" in sys.argv

    matches = load_json(MATCH_FILE)
    decisions = load_json(DECISION_FILE)
    crm_snapshot = load_json(CRM_FILE)

    match_by_url = {
        item["website_url"]: item
        for item in matches
    }

    snapshot_by_id = {
        item["account_id"]: item
        for item in crm_snapshot
    }

    # Verify every intended action is explicitly approved.
    for city, config in FACILITIES.items():
        match = next(
            (
                item for item in matches
                if city.lower() in item["website_name"].lower()
            ),
            None,
        )

        if not match:
            raise RuntimeError(f"No website match found for {city}")

        decision = decisions.get(match["website_url"], {}).get(
            "decision", "PENDING"
        )

        if decision != "APPROVED":
            raise RuntimeError(f"{city} is not approved")

        if match.get("crm_account_id") != config["old_id"]:
            raise RuntimeError(f"Unexpected CRM ID for {city}")

        if city not in match["website_name"]:
            raise RuntimeError(f"Unexpected facility identity for {city}")

        if city in ("Tiffin", "Marietta"):
            if not match.get("parent_recommendation", "").startswith("CREATE NEW"):
                raise RuntimeError(f"Unexpected recommendation for {city}")
        else:
            if not match.get("parent_recommendation", "").startswith("REPARENT"):
                raise RuntimeError(f"Unexpected recommendation for {city}")

        if config["old_id"] not in snapshot_by_id:
            raise RuntimeError(f"Missing CRM snapshot for {city}")

    # Read all live records before making any changes.
    all_accounts = get_all_accounts()
    account_map = {a["account_id"]: a for a in all_accounts}

    originals = {}

    for city, config in FACILITIES.items():
        live = api_get(f"/accounts/{config['old_id']}")
        verify_original_account(live, config)

        if config["action"] == "REPARENT" and float(
            live.get("outstanding_ar") or 0
        ) > 0:
            raise RuntimeError(
                f"Outstanding AR prevents reparenting {city}"
            )

        originals[city] = live

    print("\nPRE-FLIGHT CHECK PASSED")
    print("Four approved facilities verified.")
    print("All original financial values match.")
    print("Pending manual-review facilities excluded.")

    if not execute:
        print("\nPLAN ONLY — no CRM records changed.")

        for city, config in FACILITIES.items():
            live = originals[city]

            if config["action"] == "REPARENT":
                if live.get("parent_id") == PARENT_ID:
                    status = "ALREADY_COMPLETE"
                else:
                    status = "REPARENT"

            else:
                successor_id = live.get("chow_current_account")

                if successor_id:
                    successor = account_map.get(successor_id)

                    if not successor:
                        raise RuntimeError(
                            f"Successor account missing for {city}"
                        )

                    if (
                        successor.get("name") != config["name"]
                        or successor.get("parent_id") != PARENT_ID
                        or any(
                            successor.get(field) != value
                            for field, value in config["address"].items()
                        )
                    ):
                        raise RuntimeError(
                            f"Successor verification failed for {city}"
                        )

                    status = "ALREADY_COMPLETE"

                else:
                    existing = find_existing_new_account(
                        all_accounts, config
                    )

                    status = (
                        "LINK_EXISTING_SUCCESSOR"
                        if existing
                        else "CREATE_AND_LINK"
                    )

            print(f"{city}: {status}")

        print("\nNo CRM records were changed.")
        return

    results = []

    # Create new accounts and link the old records.
    for city in ("Tiffin", "Marietta"):
        config = FACILITIES[city]
        old_id = config["old_id"]
        old_account = api_get(f"/accounts/{old_id}")

        if old_account.get("chow_current_account"):
            new_id = old_account["chow_current_account"]
            new_account = api_get(f"/accounts/{new_id}")

            if (
                new_account.get("name") != config["name"]
                or new_account.get("parent_id") != PARENT_ID
            ):
                raise RuntimeError(
                    f"Existing successor link is unexpected for {city}"
                )

            action = "EXISTING_SUCCESSOR_REUSED"

        else:
            existing = find_existing_new_account(all_accounts, config)

            if existing:
                new_id = existing["account_id"]
                action = "EXISTING_CREATED_ACCOUNT_REUSED"
            else:
                payload = {
                    "name": config["name"],
                    "parent_id": PARENT_ID,
                    **config["address"],
                    "note": (
                        "Created through approved Bellhaven reconciliation. "
                        "Phone and care type left for verification because "
                        "source values conflict with the prior CRM record. "
                        "Original account retained for financial history."
                    ),
                }

                created = api_post(payload)
                new_id = created["account_id"]
                action = "NEW_ACCOUNT_CREATED"

            new_account = api_get(f"/accounts/{new_id}")

            if (
                new_account.get("name") != config["name"]
                or new_account.get("parent_id") != PARENT_ID
                or any(
                    new_account.get(field) != value
                    for field, value in config["address"].items()
                )
            ):
                raise RuntimeError(
                    f"New account verification failed for {city}"
                )

            link_result = api_patch(
                old_id,
                {"chow_current_account": new_id},
            )

            old_after = api_get(f"/accounts/{old_id}")
            verify_preserved(
                originals[city],
                old_after,
                {"chow_current_account"},
            )

            if old_after.get("chow_current_account") != new_id:
                raise RuntimeError(
                    f"Successor link verification failed for {city}"
                )

        results.append({
            "facility": city,
            "action": action,
            "old_account_id": old_id,
            "new_account_id": new_id,
            "verified": True,
        })

        print(f"{city}: {action}; new account {new_id}; verified.")

    # Reparent Lima and Findlay, changing only parent_id.
    for city in ("Lima", "Findlay"):
        config = FACILITIES[city]
        account_id = config["old_id"]
        before = originals[city]

        if before.get("parent_id") == PARENT_ID:
            action = "ALREADY_CORRECT"
        else:
            api_patch(account_id, {"parent_id": PARENT_ID})
            action = "REPARENTED"

        after = api_get(f"/accounts/{account_id}")

        if after.get("parent_id") != PARENT_ID:
            raise RuntimeError(f"Parent verification failed for {city}")

        verify_preserved(
            before,
            after,
            {"parent_id", "parent_name"},
        )

        results.append({
            "facility": city,
            "action": action,
            "account_id": account_id,
            "verified": True,
        })

        print(f"{city}: {action}; parent and financial values verified.")

    report = {
        "mode": "LIVE_WRITEBACK",
        "parent_id": PARENT_ID,
        "facilities_processed": len(results),
        "verified": all(item["verified"] for item in results),
        "results": results,
    }

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("\nLIVE WRITEBACK COMPLETE")
    print("Facilities processed:", len(results))
    print("All updates verified:", report["verified"])
    print("Report:", REPORT_FILE)


if __name__ == "__main__":
    main()
