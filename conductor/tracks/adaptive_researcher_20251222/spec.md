# Specification: Phase 1 - The "Adaptive Researcher" (LangGraph Refactor)

## Overview
Refactor the current linear `Fetch -> Extract -> Save` pipeline into an agentic workflow using LangGraph. This "Adaptive Researcher" agent will triage posts for relevance, perform extraction, critique its own work, and proactively gather more context (comments/related posts) if the initial signal is weak or lacks sufficient evidence.

## Functional Requirements

### 1. LangGraph Workflow Implementation
- Create a new module `src/pain_radar/agent/graph.py` to house the `StateGraph`.
- **State Definition:** Include the original post, current extraction, critique score, and an attempt counter to prevent infinite loops.

### 2. Agent Nodes
- **Triage Node:** Use **GPT-4o-mini** to classify posts.
    - *Criteria:* Relevant posts must contain a problem, struggle, or "how do I" question.
    - *Outcome:* Immediately ends processing for spam or irrelevant content.
- **Extract Node:** Adapt existing `analyze_post` logic to extract pain signals and supporting quotes.
- **Reflect Node:** Self-critique the extraction based on two primary pillars:
    - **Evidence Strength:** Do the quotes directly and substantially support the pain point?
    - **Actionability:** Is the identified problem potentially solvable by a product or service?
    - *Outcome:* Returns a score (0-10).
- **Expand Node (Tools):** Triggered if the Reflect score is below 7.
    - **Tool: `fetch_more_comments`**: Retrieve deeper comment threads for the current post.
    - **Tool: `search_related_posts`**: Execute a search for similar titles within the same subreddit to find corroborating evidence.

### 3. Workflow Transitions
- `Triage` -> `Extract` (if relevant) or `END` (if irrelevant).
- `Extract` -> `Reflect`.
- `Reflect` -> `Expand` (if score < 7 and attempts < 2).
- `Expand` -> `Extract` (loop back with additional context).
- `Reflect` -> `END` (if score >= 7 or max attempts reached).

### 4. Integration
- Update `src/pain_radar/pipeline.py` to utilize the compiled LangGraph `app` for post processing.

## Non-Functional Requirements
- **Efficiency:** Drastically reduce GPT-4o usage by using GPT-4o-mini for the Triage and initial Triage steps.
- **Resilience:** Gracefully handle API failures within tool calls.

## Acceptance Criteria
- [ ] LangGraph workflow successfully replaces the linear processing logic.
- [ ] Triage node correctly filters out at least 80% of irrelevant test posts.
- [ ] Reflect node correctly identifies "weak" extractions.
- [ ] Expand node successfully retrieves and integrates additional data into a second extraction attempt.
- [ ] Unit tests cover each node individually and the full graph traversal.
