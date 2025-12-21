# Track Plan: Unit Tests for Core Analysis Logic

## Phase 1: Setup and Infrastructure [checkpoint: f049455]
- [x] Task: Set up test environment and directory structure. <!-- id: 56be826 -->
    - Create `tests/` directory if it doesn't exist.
    - Create `tests/test_analyze.py` and `tests/test_cluster.py`.
    - Configure `pytest` fixtures for mocking dependencies.
- [x] Task: Conductor - User Manual Verification 'Setup and Infrastructure' (Protocol in workflow.md)

## Phase 2: Testing Analysis Logic (`src/pain_radar/analyze.py`)
- [x] Task: Write tests for `extract_pain_signals`. <!-- id: 0d5c1a4 -->
    - Mock LLM response.
    - Test positive cases (valid pain signals).
    - Test negative cases (no pain signals).
- [x] Task: Write tests for filtering logic. <!-- id: 9f321d8 -->
    - Test filtering of self-promotion.
    - Test filtering of irrelevant posts.
- [x] Task: Write tests for error handling. <!-- id: 088c6c3 -->
    - Test behavior when LLM API fails.
    - Test behavior with malformed input.
- [ ] Task: Conductor - User Manual Verification 'Testing Analysis Logic' (Protocol in workflow.md)

## Phase 3: Testing Clustering Logic (`src/pain_radar/cluster.py`)
- [ ] Task: Write tests for `cluster_signals`.
    - Mock LLM response for embedding/clustering.
    - Test clustering of identical/similar signals.
    - Test handling of distinct signals.
- [ ] Task: Write tests for cluster metadata generation.
    - Verify cluster naming and summary generation.
- [ ] Task: Conductor - User Manual Verification 'Testing Clustering Logic' (Protocol in workflow.md)

## Phase 4: Review and Refine
- [ ] Task: Run full test suite and check coverage.
    - Execute `pytest --cov=src/pain_radar`.
    - Ensure coverage meets the 80% target.
- [ ] Task: Refactor code if necessary to improve testability or fix bugs discovered during testing.
- [ ] Task: Conductor - User Manual Verification 'Review and Refine' (Protocol in workflow.md)
