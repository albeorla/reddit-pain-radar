# Track Plan: Comprehensive Local Verification and Coverage

## Phase 1: Storage Layer Testing (`src/pain_radar/store/`) [checkpoint: be26e9f]
- [x] Task: Write tests for database initialization and connectivity. <!-- id: 7be4c81 -->
- [x] Task: Write tests for CRUD operations on Signal models. <!-- id: e07f82f -->
- [x] Task: Write tests for CRUD operations on Source and SourceSet models. <!-- id: 6b50c16 -->
- [x] Task: Conductor - User Manual Verification 'Storage Layer Testing' (Protocol in workflow.md)

## Phase 2: Pipeline and CLI Testing (`src/pain_radar/pipeline.py` & `src/pain_radar/cli/`)
- [x] Task: Write unit tests for `pipeline.py` (mocking reddit and LLM). <!-- id: e6fcfde -->
- [x] Task: Write tests for CLI command registration and arguments (using `CliRunner`). <!-- id: 4e0dcce -->
- [~] Task: Write integration tests for `fetch` and `run` commands (mocking network).
- [ ] Task: Conductor - User Manual Verification 'Pipeline and CLI Testing' (Protocol in workflow.md)

## Phase 3: Web and API Testing (`src/pain_radar/web_app.py` & `src/pain_radar/api/`)
- [ ] Task: Write tests for web routes (Dashboard, Signal Detail) using `TestClient`.
- [ ] Task: Write tests for API v1 endpoints (CRUD via JSON).
- [ ] Task: Conductor - User Manual Verification 'Web and API Testing' (Protocol in workflow.md)

## Phase 4: Scripted Verification Suite
- [ ] Task: Create a repeatable verification script (`scripts/verify_local.sh`).
    - The script should:
        1. Initialize a temporary test database.
        2. Run a full `fetch` -> `run` -> `cluster` -> `digest` cycle using mocks.
        3. Start the FastAPI server in a background process.
        4. Use `curl` or a python script to check key endpoints.
        5. Stop the server and clean up.
- [ ] Task: Conductor - User Manual Verification 'Scripted Verification Suite' (Protocol in workflow.md)

## Phase 5: Coverage Finalization
- [ ] Task: Run the full test suite and verify >80% coverage.
    - Execute `pytest --cov=src/pain_radar`.
    - Identify and address any remaining coverage gaps in core logic.
- [ ] Task: Conductor - User Manual Verification 'Coverage Finalization' (Protocol in workflow.md)
