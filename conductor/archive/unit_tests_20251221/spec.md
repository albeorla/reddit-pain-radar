# Track Specification: Unit Tests for Core Analysis Logic

## Goal
Implement comprehensive unit tests for the core analysis logic in `src/pain_radar/analyze.py` and related modules. This will ensure the reliability of the pain signal extraction and clustering algorithms, and provide a safety net for future refactoring and feature additions.

## Context
The project currently lacks comprehensive unit tests for its core logic. As the project evolves, having a robust test suite is crucial for maintaining code quality and preventing regressions. The analysis logic is central to the application's value proposition, making it a high-priority target for testing.

## Scope
-   **Target Modules:**
    -   `src/pain_radar/analyze.py`: Pain signal extraction and classification.
    -   `src/pain_radar/cluster.py`: Clustering of pain points.
    -   `src/pain_radar/models.py`: Data models used in analysis (if they contain logic).
-   **Test Framework:** Pytest (as per `pyproject.toml`).
-   **Mocking:** Use standard `unittest.mock` or `pytest-mock` to mock external dependencies like the OpenAI API and database calls.

## Requirements
1.  **Test Coverage:** Aim for high coverage (>80%) of the target modules.
2.  **Test Cases:**
    -   **`analyze.py`:**
        -   Test extraction of different signal types (pain, willingness_to_pay, etc.).
        -   Test filtering of self-promotion posts.
        -   Test handling of edge cases (empty posts, malformed data).
        -   Mock LLM responses to ensure deterministic testing.
    -   **`cluster.py`:**
        -   Test clustering of similar signals.
        -   Test handling of diverse and unrelated signals.
        -   Test cluster naming and description generation (mocking LLM).
3.  **Refactoring:** Minor refactoring of the code may be necessary to make it more testable (e.g., dependency injection).

## Non-Goals
-   Integration tests with live Reddit or OpenAI APIs.
-   UI/CLI testing (covered in separate tracks).

## Success Metrics
-   All new tests pass.
-   Code coverage for target modules exceeds 80%.
-   CI pipeline (if configured) runs these tests successfully.
