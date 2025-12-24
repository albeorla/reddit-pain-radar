# Implementation Plan - Phase 1: The "Adaptive Researcher" (LangGraph Refactor)

This plan outlines the refactoring of the Reddit pain point extraction pipeline into an agentic workflow using LangGraph.

## Phase 1: Setup and Foundation [checkpoint: 8a6fea5]
- [x] Task: Install and Configure Dependencies (Add `langgraph` and `langchain-openai` to `pyproject.toml`) ae07405
- [x] Task: Define Agent State and Models (Create `src/pain_radar/agent/models.py`) cde2c0c
- [x] Task: Conductor - User Manual Verification 'Phase 1: Setup and Foundation' (Protocol in workflow.md)

## Phase 2: Research Tools Implementation
- [x] Task: Implement `fetch_more_comments` tool in `src/pain_radar/reddit_async.py` 6b2191b
- [x] Task: Implement `search_related_posts` tool in `src/pain_radar/reddit_async.py` 5021e3a
- [x] Task: Create Tool abstraction for the Agent in `src/pain_radar/agent/tools.py` 5cbc194
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Research Tools Implementation' (Protocol in workflow.md)

## Phase 3: Agent Node Development
- [ ] Task: Implement `triage_node` (GPT-4o-mini classification) in `src/pain_radar/agent/nodes.py`
- [ ] Task: Implement `extract_node` (Integration of existing analysis) in `src/pain_radar/agent/nodes.py`
- [ ] Task: Implement `reflect_node` (Self-critique logic) in `src/pain_radar/agent/nodes.py`
- [ ] Task: Implement `expand_node` (Tool execution logic) in `src/pain_radar/agent/nodes.py`
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Agent Node Development' (Protocol in workflow.md)

## Phase 4: Graph Construction and Integration
- [ ] Task: Assemble and Compile the StateGraph in `src/pain_radar/agent/graph.py`
- [ ] Task: Refactor `src/pain_radar/pipeline.py` to use the Agentic Graph
- [ ] Task: Update CLI/Configuration to support the new agentic workflow
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Graph Construction and Integration' (Protocol in workflow.md)

## Phase 5: Final Verification and Cleanup
- [ ] Task: Perform End-to-End Integration Tests for the Agentic Loop
- [ ] Task: Verify Cost/Usage metrics (Mini-model triage effectiveness)
- [ ] Task: Conductor - User Manual Verification 'Phase 5: Final Verification and Cleanup' (Protocol in workflow.md)
