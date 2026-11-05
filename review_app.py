
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import streamlit as st


# --------------------------------------------------
# FILE LOCATIONS
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent

MATCHING_FILE = PROJECT_DIR / "reports" / "matching_results.json"
DECISIONS_FILE = PROJECT_DIR / "reports" / "review_decisions.json"
DUPLICATES_FILE = PROJECT_DIR / "reports" / "crm_duplicate_candidates.json"


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Bellhaven CRM Reconciliation",
    page_icon="🏥",
    layout="wide"
)

st.title("Bellhaven CRM Reconciliation")
st.caption(
    "Review website-to-CRM matches, inspect evidence, "
    "and record approval decisions."
)

st.warning(
    "Review mode only: decisions are saved locally. "
    "No changes are being sent to the CRM."
)


# --------------------------------------------------
# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

@st.cache_data
def load_matching_results():
    if not MATCHING_FILE.exists():
        raise FileNotFoundError(
            "Matching results not found. Run matcher.py first."
        )

    with open(MATCHING_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def load_decisions():
    if not DECISIONS_FILE.exists():
        return {}

    with open(DECISIONS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


@st.cache_data
def load_duplicate_candidates():
    if not DUPLICATES_FILE.exists():
        return []

    with open(DUPLICATES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_decisions(decisions):
    DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = DECISIONS_FILE.with_suffix(".tmp")

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(decisions, file, indent=2, ensure_ascii=False)

    temporary_file.replace(DECISIONS_FILE)


try:
    results = load_matching_results()
    decisions = load_decisions()
    duplicate_groups = load_duplicate_candidates()

except Exception as error:
    st.error(f"Unable to load project data: {error}")
    st.stop()


# --------------------------------------------------
# RESTORE PREVIOUS DECISIONS
# --------------------------------------------------

for result in results:
    key = result.get("website_url") or result.get("website_name")

    if key in decisions:
        result["decision"] = decisions[key]["decision"]
    else:
        result["decision"] = "PENDING"


# --------------------------------------------------
# SUMMARY METRICS
# --------------------------------------------------

total = len(results)
pending = sum(r["decision"] == "PENDING" for r in results)
approved = sum(r["decision"] == "APPROVED" for r in results)
rejected = sum(r["decision"] == "REJECTED" for r in results)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Website communities", total)
col2.metric("Pending review", pending)
col3.metric("Approved", approved)
col4.metric("Rejected", rejected)

st.divider()


# --------------------------------------------------
# FILTERS
# --------------------------------------------------

st.subheader("Review queue")

filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    decision_filter = st.selectbox(
        "Decision status",
        ["PENDING", "APPROVED", "REJECTED", "ALL"]
    )

with filter_col2:
    review_filter = st.selectbox(
        "Matching category",
        [
            "ALL",
            "LIKELY MATCH - VERIFY",
            "MANUAL REVIEW",
            "POSSIBLY MISSING FROM CRM"
        ]
    )


filtered_results = []

for result in results:
    if decision_filter != "ALL":
        if result.get("decision") != decision_filter:
            continue

    if review_filter != "ALL":
        if result.get("review_status") != review_filter:
            continue

    filtered_results.append(result)


if not filtered_results:
    st.info("No records match these filters.")
    st.stop()


# --------------------------------------------------
# REVIEW SUMMARY TABLE
# --------------------------------------------------

table_data = []

for result in filtered_results:
    table_data.append({
        "Website facility": result.get("website_name"),
        "CRM account": result.get("crm_name") or "No selected account",
        "Match score": result.get("match_score"),
        "Review category": result.get("review_status"),
        "Parent recommendation": result.get("parent_recommendation"),
        "Decision": result.get("decision")
    })

st.dataframe(
    pd.DataFrame(table_data),
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# SELECT A FACILITY
# --------------------------------------------------

st.divider()
st.subheader("Inspect a facility")

facility_options = [
    f"{r.get('website_name')} | {r.get('decision')} | "
    f"{r.get('review_status')}"
    for r in filtered_results
]

selected_option = st.selectbox(
    "Select a facility to review",
    facility_options
)

selected_index = facility_options.index(selected_option)
record = filtered_results[selected_index]

website_key = record.get("website_url") or record.get("website_name")


# --------------------------------------------------
# WEBSITE AND CRM DETAILS
# --------------------------------------------------

st.divider()

website_col, crm_col = st.columns(2)

with website_col:
    st.markdown("### Website information")

    st.write("**Facility:**", record.get("website_name"))
    st.write("**Address:**", record.get("website_address"))
    st.write("**Phone:**", record.get("website_phone"))

    if record.get("website_url"):
        st.markdown(
            f"[Open website facility page]({record['website_url']})"
        )

with crm_col:
    st.markdown("### CRM information")

    st.write(
        "**Account:**",
        record.get("crm_name") or "No selected CRM account"
    )
    st.write(
        "**Account ID:**",
        record.get("crm_account_id") or "No account selected"
    )
    st.write("**Address:**", record.get("crm_address") or "Not available")
    st.write("**Phone:**", record.get("crm_phone") or "Not available")
    st.write(
        "**Current parent:**",
        record.get("crm_parent_name") or "No parent"
    )


# --------------------------------------------------
# --------------------------------------------------
# ALTERNATIVE CRM CANDIDATE
# --------------------------------------------------

if not record.get("crm_account_id") and record.get("name_only_candidate_name"):
    st.divider()
    st.subheader("Alternative CRM candidate - name similarity only")

    st.warning(
        "This account was identified by name similarity only. "
        "Its physical location has not been verified. "
        "Do not approve it as a match without further investigation."
    )

    st.write(
        "**Candidate name:**",
        record.get("name_only_candidate_name")
    )

    st.write(
        "**Candidate ID:**",
        record.get("name_only_candidate_id")
    )

    st.write(
        "**Candidate address:**",
        record.get("name_only_candidate_address")
    )

    st.write(
        "**Name similarity:**",
        f"{record.get('name_only_candidate_name_score', 0):.2f}%"
    )
# MATCHING EVIDENCE
# --------------------------------------------------

st.divider()
st.subheader("Matching evidence")

score1, score2, score3 = st.columns(3)

score1.metric("Overall match score", f"{record.get('match_score', 0):.2f}%")
score2.metric("Name similarity", f"{record.get('name_score', 0):.2f}%")
score3.metric(
    "Physical location match",
    "Yes" if record.get("location_match") else "No"
)

with st.expander("View detailed matching scores"):
    st.write("**Street score:**", record.get("street_score"))
    st.write("**City score:**", record.get("city_score"))
    st.write("**State score:**", record.get("state_score"))
    st.write("**ZIP score:**", record.get("zip_score"))
    st.write(
        "**Address conflicts:**",
        record.get("address_conflicts") or "None recorded"
    )
    st.write(
        "**Candidate collision:**",
        record.get("candidate_collision")
    )
    st.write(
        "**Collision with:**",
        record.get("candidate_collision_with") or "None"
    )

with st.expander("View second-best CRM candidate"):
    st.write("**Candidate:**", record.get("second_candidate") or "None")
    st.write("**Account ID:**", record.get("second_candidate_id") or "None")
    st.write(
        "**Candidate score:**",
        record.get("second_candidate_score")
    )
    # --------------------------------------------------
# DUPLICATE ACCOUNT EVIDENCE
# --------------------------------------------------

selected_crm_id = record.get("crm_account_id")

matching_duplicate_groups = [
    group
    for group in duplicate_groups
    if any(
        account.get("account_id") == selected_crm_id
        for account in group.get("accounts", [])
    )
]

with st.expander("View CRM accounts sharing this address"):

    if matching_duplicate_groups:
        for group in matching_duplicate_groups:
            st.write("**Shared physical address:**", group.get("normalized_address"))

            duplicate_table = []

            for account in group.get("accounts", []):
                duplicate_table.append({
                    "Account name": account.get("name"),
                    "Account ID": account.get("account_id"),
                    "Phone": account.get("phone"),
                    "Parent company": account.get("parent_name"),
                    "Status": account.get("status"),
                    "Lifetime revenue": account.get("lifetime_revenue"),
                    "Outstanding AR": account.get("outstanding_ar")
                })

            st.dataframe(
                pd.DataFrame(duplicate_table),
                use_container_width=True,
                hide_index=True
            )

            st.warning(
                "Accounts sharing an address are not automatically duplicates. "
                "Verify facility identity and ownership before changing CRM records."
            )

    else:
        st.info(
            "No shared-address CRM account group was found for this selected account."
        )


# --------------------------------------------------
# BILLING AND PARENT ACCOUNT REVIEW
# --------------------------------------------------

st.divider()
st.subheader("Billing and parent-account review")

billing_col1, billing_col2 = st.columns(2)

with billing_col1:
    st.metric(
        "Lifetime revenue",
        f"${record.get('lifetime_revenue', 0):,.2f}"
    )

with billing_col2:
    st.metric(
        "Outstanding AR",
        f"${record.get('outstanding_ar', 0):,.2f}"
    )

recommendation = record.get("parent_recommendation", "")

st.write("**Recommended action:**", recommendation)

if (
    record.get("lifetime_revenue", 0) > 0
    and record.get("outstanding_ar", 0) > 0
):
    st.error(
        "Billing safeguard: This account has revenue history AND "
        "outstanding AR. Do not directly re-parent or deactivate it. "
        "The recommended process is to preserve the old account "
        "and create a new account under the correct parent."
    )

elif recommendation.startswith("CREATE NEW"):
    st.warning(
        "A new Bellhaven account is recommended. "
        "Preserve the existing account and its financial history."
    )

elif recommendation.startswith("REPARENT"):
    st.warning(
        "Review the account's billing history and parent relationship "
        "before approving a re-parenting action."
    )

elif "MANUAL REVIEW" in recommendation:
    st.warning(
        "The matching evidence is insufficient for an automatic "
        "parent-account decision."
    )


# --------------------------------------------------
# APPROVAL AND REJECTION
# --------------------------------------------------

st.divider()
st.subheader("Record review decision")

st.write("**Current decision:**", record.get("decision"))

review_note = st.text_area(
    "Reviewer notes",
    placeholder=(
        "Explain why this proposal should be approved or rejected. "
        "Record any evidence that needs follow-up."
    ),
    key=f"notes_{website_key}"
)

requires_extra_review = (
    recommendation != "NO PARENT CHANGE NEEDED"
    or record.get("lifetime_revenue", 0) > 0
    or record.get("outstanding_ar", 0) > 0
    or not record.get("location_match", False)
    or record.get("review_status") != "LIKELY MATCH - VERIFY"
)

if requires_extra_review:
    reviewed_billing = st.checkbox(
        "I have reviewed the match evidence, parent recommendation, "
        "and billing implications."
    )
else:
    reviewed_billing = True

approve_col, reject_col = st.columns(2)

with approve_col:
    approve_clicked = st.button(
        "Approve proposal",
        type="primary",
        use_container_width=True,
        disabled=(record.get("decision") != "PENDING")
    )

with reject_col:
    reject_clicked = st.button(
        "Reject proposal",
        use_container_width=True,
        disabled=(record.get("decision") != "PENDING")
    )


if approve_clicked:
    if not reviewed_billing:
        st.error("Please confirm that you reviewed the evidence first.")
    elif not review_note.strip():
        st.error("Please enter a reviewer note before approving.")
    else:
        decisions[website_key] = {
            "website_name": record.get("website_name"),
            "crm_account_id": record.get("crm_account_id"),
            "decision": "APPROVED",
            "review_note": review_note.strip(),
            "reviewed_at": datetime.now(timezone.utc).isoformat()
        }

        save_decisions(decisions)
        st.success("Approval saved locally. No CRM update was performed.")
        st.rerun()


if reject_clicked:
    if not review_note.strip():
        st.error("Please enter a reason for rejecting this proposal.")
    else:
        decisions[website_key] = {
            "website_name": record.get("website_name"),
            "crm_account_id": record.get("crm_account_id"),
            "decision": "REJECTED",
            "review_note": review_note.strip(),
            "reviewed_at": datetime.now(timezone.utc).isoformat()
        }

        save_decisions(decisions)
        st.success("Rejection saved locally. No CRM update was performed.")
        st.rerun()


# --------------------------------------------------
# DECISION HISTORY
# --------------------------------------------------

st.divider()
st.subheader("Saved decision history")

if decisions:
    history = []

    for item in decisions.values():
        history.append({
            "Website facility": item.get("website_name"),
            "CRM account ID": item.get("crm_account_id"),
            "Decision": item.get("decision"),
            "Reviewer notes": item.get("review_note"),
            "Reviewed at": item.get("reviewed_at")
        })

    st.dataframe(
        pd.DataFrame(history),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No approval or rejection decisions have been saved yet.")

st.caption(
    "Bellhaven CRM Reconciliation | Local review application | "
    "CRM writeback is not enabled."
)
