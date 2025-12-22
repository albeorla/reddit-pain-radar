# Track Specification: Comprehensive Local Verification and Coverage

## Overview
This track focuses on ensuring the entire Pain Radar system is fully functional locally and meets a minimum code coverage requirement of 80%. This will be achieved by implementing a scripted, repeatable verification suite and backfilling unit and integration tests across all modules.

## Functional Requirements
1. **Scripted Verification Suite:**
    - Develop a repeatable script (e.g., `scripts/verify_local.sh` or a Python equivalent) that performs a full system smoke test.
    - **Pipeline Check:** Simulate a data run: initialize database, fetch sample data (mocked or small subset), run analysis, cluster results, and generate a digest.
    - **API & Web Check:** Start the FastAPI application and verify that key endpoints (Dashboard, Signals) respond successfully.
    - **Storage Check:** Verify database connectivity and basic CRUD operations for signal and source records.
2. **Comprehensive Test Coverage:**
    - Implement missing unit and integration tests for the following high-priority areas:
        - `src/pain_radar/cli/`: Verify CLI command registration and basic invocation logic.
        - `src/pain_radar/store/`: Ensure robust database interactions and schema integrity.
        - `src/pain_radar/pipeline.py`: Test the end-to-end flow of the analysis pipeline.
        - `src/pain_radar/web_app.py` & `src/pain_radar/api/`: Verify web routes and API logic using `TestClient`.

## Non-Functional Requirements
- **Test Coverage:** Minimum 80% coverage across the entire `src/` directory.
- **Repeatability:** The verification script must be executable with a single command and produce a clear "Success" or "Failure" output.
- **CI Readiness:** The tests and verification script should be designed to run in a CI environment (using mocks for external API dependencies).

## Acceptance Criteria
- [ ] A repeatable verification script exists and passes all checks.
- [ ] The global test suite (unit + integration) runs successfully.
- [ ] Total code coverage for the `src/` directory is >= 80%.
- [ ] The web server can be started and key endpoints verified via script.

## Out of Scope
- Performance benchmarking or stress testing.
- UI/UX design improvements (focus is on functional verification).
- Live integration with Reddit API (will use mocks or cached data for verification).
