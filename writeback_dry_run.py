import json
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent

MATCHING_FILE = BASE_DIR / "reports" / "matching_results.json"
DECISIONS_FILE = BASE_DIR / "reports" / "review_decisions.json"
CRM_FILE = BASE_DIR / "data" / "crm_accounts.json"
OUTPUT_FILE = BASE_DIR / "reports" / "writeback_dry_run.json"

BELLHAVEN_PARENT_ID = "0015QAPLGS3FVYEEEM"


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def main():
    matches = load_json(MATCHING_FILE)
    decisions = load_json(DECISIONS_FILE)
    crm_accounts = load_json(CRM_FILE)

    crm_by_id = {
        account["account_id"]: account
        for account in crm_accounts
    }

    results = []

    for match in matches:
        website_url = match.get("website_url", "")
        decision_record = decisions.get(website_url, {})

        decision = decision_record.get("decision", "PENDING")
        recommendation = match.get("parent_recommendation", "")
        account_id = match.get("crm_account_id")
        account = crm_by_id.get(account_id)

        result = {
            "facility": match.get("website_name"),
            "crm_account_id": account_id,
            "decision": decision,
            "recommendation": recommendation,
            "action": "",
            "reason": "",
        }

        if not account and account_id:
            result["action"] = "BLOCKED"
            result["reason"] = "CRM account ID not found."

        elif recommendation.startswith("NO PARENT CHANGE"):
            if decision == "APPROVED":
                result["action"] = "NO_CHANGE"
                result["reason"] = "Approved match; no parent update needed."
            else:
                result["action"] = "PENDING_APPROVAL"
                result["reason"] = "Match has not been approved."

        elif recommendation.startswith("REPARENT"):
            if decision != "APPROVED":
                result["action"] = "PENDING_APPROVAL_REPARENT"
                result["reason"] = "Parent correction requires approval."
            elif float(account.get("outstanding_ar") or 0) > 0:
                result["action"] = "BLOCKED"
                result["reason"] = "Outstanding AR prevents direct reparenting."
            elif account.get("parent_id") == BELLHAVEN_PARENT_ID:
                result["action"] = "NO_CHANGE"
                result["reason"] = "Account already has the correct parent."
            else:
                result["action"] = "REPARENT_REQUIRES_VERIFIED_API"
                result["reason"] = (
                    "Approved parent correction. API payload must be verified "
                    "before any live update."
                )

        elif recommendation.startswith("CREATE NEW"):
            if decision != "APPROVED":
                result["action"] = "PENDING_APPROVAL_NEW_ACCOUNT"
                result["reason"] = (
                    "New account proposal requires approval. Preserve old "
                    "account and financial history."
                )
            else:
                result["action"] = "NEW_ACCOUNT_REQUIRES_VERIFIED_API"
                result["reason"] = (
                    "Approved proposal. Create a new account only after "
                    "verifying the API payload and required fields."
                )

        else:
            result["action"] = "MANUAL_REVIEW"
            result["reason"] = (
                "Identity, location, or duplicate-account issue requires "
                "manual investigation."
            )

        results.append(result)

    counts = {}

    for item in results:
        action = item["action"]
        counts[action] = counts.get(action, 0) + 1

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "DRY_RUN_ONLY",
        "crm_updates_performed": 0,
        "facilities_evaluated": len(results),
        "action_counts": counts,
        "results": results,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    print("COMPLETE RECONCILIATION DRY RUN")
    print("Facilities evaluated:", len(results))
    print("CRM updates performed: 0")
    print("\nACTION SUMMARY:")

    for action, count in sorted(counts.items()):
        print(f"{action}: {count}")

    print("\nReport saved to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()