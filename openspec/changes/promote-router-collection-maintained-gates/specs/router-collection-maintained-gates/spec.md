## ADDED Requirements

### Requirement: Stable router suites are promoted to maintained backend gates

Image router and collection API legacy test suites SHALL run in maintained backend gates once they pass together in a targeted stability run.

#### Scenario: Router suites pass targeted stability
- **WHEN** `python -m pytest tests/test_images_router.py tests/test_api_collection.py -q` runs
- **THEN** both files pass together without failures or errors

#### Scenario: Local maintained gates include promoted router suites
- **WHEN** the local contract or maintained backend coverage gate runs
- **THEN** `tests/test_images_router.py` and `tests/test_api_collection.py` are included in the curated pytest list

#### Scenario: CI maintained gates include promoted router suites
- **WHEN** backend maintained CI or maintained coverage CI runs
- **THEN** `tests/test_images_router.py` and `tests/test_api_collection.py` are included in the curated pytest list

#### Scenario: Legacy triage reflects promotion
- **WHEN** the legacy failure inventory is consulted
- **THEN** the image router and collection API suites are no longer listed as unpromoted follow-ups
