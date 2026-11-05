# Bellhaven CRM Reconciliation



## Overview

Python project to reconcile Bellhaven website communities against CRM accounts, identify potential matches and discrepancies, and provide a human review workflow.



## Data Sources

- Bellhaven website directory and facility pages

- CRM REST API

- 35 website communities collected

- 121 CRM accounts retrieved



## Run Locally



Install dependencies:

```bash

pip install -r requirements.txt

```



Create a `.env` file using `.env.example`. Add your candidate API token. Never commit `.env`.



Run the scraper:

```bash

python scraper.py

```



Run matching:

```bash

python matcher.py

```



Launch the review application:

```bash

python -m streamlit run review_app.py

```



Run automated tests:

```bash

python -m pytest -q

```



Run the writeback dry run:

```bash

python writeback_dry_run.py

```



## Matching Approach

Weighted fuzzy matching:

- Facility name: 60%

- Street: 15%

- City: 10%

- State: 5%

- ZIP code: 10%



Location checks and conflicting candidate records help identify likely matches and records requiring manual review.



## Review Workflow

The Streamlit application displays website and CRM details, candidate scores, conflicts, and recommendations.



Approval and rejection decisions are stored locally in `reports/review_decisions.json`. The matcher restores saved decisions on subsequent runs.



## Latest Matching Results

- Website communities: 35

- CRM accounts: 121

- Likely matches: 20

- Manual review: 15

- Locally approved decisions: 20

- Pending decisions: 15

- Possible duplicate address groups: 6



## Writeback Dry Run

The dry-run process evaluates proposed actions without changing CRM records.



Latest dry-run summary:

- Manual review: 14

- New account actions requiring verified API details: 2

- Reparent actions requiring verified API details: 2

- No change: 16

- Pending approval: 1

- CRM updates performed: 0



## Automated Tests

The test suite contains 10 tests covering text normalization, similarity scoring, address parsing, candidate scoring, and location conflict detection.



Latest test result: 10 passed.



## Limitations and Next Steps

- No live CRM updates have been performed.

- The available API documentation does not specify the required account create/update request body. Writeback must be implemented only after the API contract is verified.

- Manual-review and pending records require further investigation.

- Duplicate-address candidates require identity verification; a shared address alone does not establish a duplicate.

- Improve address normalization, phone comparisons, and missing-account classification.

- Validate idempotent writeback behavior and daily scheduling.

- Expand automated tests for API integration and reconciliation edge cases.



