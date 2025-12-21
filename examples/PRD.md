# PRD: Pain Radar Pro (Paid Weekly Digest + API)

## 1) Context and current baseline

**Pain Radar today** is a CLI-first tool that fetches public Reddit posts, analyzes them with an LLM to extract “pain signals,” clusters them, and generates a Reddit-ready weekly digest with quotes and links. ([GitHub][1])
It already has the core workflow (`fetch` → `run` → `cluster` → `digest`) and “watchlists/alerts” concepts in the CLI docs. ([GitHub][1])

**The pivot you’re proposing:** turn the engine into a paid product with:

* **Weekly digest subscription** (delivered to email, dashboard, webhook, RSS)
* **API access** (programmatic access to signals, clusters, digests, and metadata)

This PRD is “based on what you have now” and explicitly calls out what must change to become a subscription SaaS.

---

## 2) Problem statement

People building products, investing, or doing research want **repeatable, trustworthy “what are people struggling with” intelligence** without spending hours on Reddit. They want it:

* tailored to their ICP and topics
* consistent (weekly)
* citeable (quotes + links)
* accessible (email/dashboard/API)
* not spammy, not scraping private data (aligned with your positioning) ([GitHub][1])

---

## 3) Goals and non-goals

### Goals (MVP)

1. **Paid subscription** that reliably delivers a weekly digest for chosen source sets (and optionally keywords).
2. **Self-serve onboarding:** create account → choose ICP/presets → configure delivery → pay → receive digest.
3. **API access** for paid users with API keys and rate limits.
4. **Archive access** in a web app (private per customer, optionally public samples).

### Non-goals (MVP)

* Real-time firehose streaming
* Fully automated “outreach” or posting (you explicitly avoid it today) ([GitHub][1])
* High-touch consulting workflows (can be a later tier add-on)

---

## 4) Target users and core JTBD

### Personas

* **Indie builder / marketer:** wants weekly “what to build / what to write about” prompts
* **Product manager:** wants recurring pain clusters for roadmap discovery
* **Investor / researcher:** wants signals across categories with evidence and trend direction
* **DevRel / platform teams:** want API access for internal dashboards

### Jobs-to-be-done

* “Tell me what pains are repeating in my ICP this week, with proof.”
* “Alert me when a topic appears repeatedly (not just one-off mentions).”
* “Let me pull clusters/signals into my own tooling via API.”

---

## 5) Product scope

### 5.1 Weekly Digest Subscription (MVP)

**Digest definition:** a weekly report (per customer configuration) containing top clusters, summary, target audience, quotes (verbatim), and source links, similar to your existing digest output. ([GitHub][1])

**Configurable inputs**

* Source sets (your existing preset concept)
* Optional custom subreddits
* Optional keyword filters (watchlist semantics)
* Time window (default 7 days)
* Max clusters (default 7)

**Delivery channels**

* Email (primary)
* Web dashboard (archive)
* Webhook (for power users)
* RSS feed (nice, low-friction)

### 5.2 API Product (MVP)

Provide endpoints for:

* **Signals** (raw extracted pain signals + evidence metadata)
* **Clusters** (cluster titles/summaries + evidence + included signal IDs)
* **Digests** (rendered Markdown + structured JSON)
* **Sources** (presets + customer configuration)

---

## 6) Functional requirements

### A) Accounts, auth, and tenancy

1. Users can sign up/login (email magic link or password; magic link is simpler).
2. Every artifact is scoped to a **tenant** (user or org):

   * source sets
   * runs
   * signals
   * clusters
   * digests
   * alert rules
3. Roles (MVP): owner; later: team members.

### B) Billing and subscriptions

1. Integrate Stripe (or equivalent):

   * Plans: Monthly/Annual
   * Entitlements: number of source sets, posts analyzed/week, API access, seats
2. Subscription status gates:

   * active: full access
   * past_due: grace period then suspend
   * canceled: archive read-only until end of term

### C) Pipeline orchestration (turn CLI into “runs per customer”)

1. Weekly scheduled job per tenant:

   * fetch posts
   * analyze a capped number of posts (cost control)
   * cluster extracted signals
   * generate digest (Markdown + JSON)
   * deliver via chosen channels
2. Manual “Run now” button for Pro users (rate-limited).
3. Cost controls:

   * hard caps per plan
   * concurrency tuning
   * caching and dedupe (you already have dedupe logic)

### D) Digest rendering

1. Output formats:

   * Email-friendly HTML
   * Markdown (for copy/paste and API)
   * JSON (for API and UI)
2. Evidence requirements:

   * include quotes and source links (your core value prop) ([GitHub][1])
3. “Confidence/evidence strength” visible in UI/API (use your `evidence_strength` concept).

### E) Alerts (keyword + cluster-level)

MVP “alerts” should be clear and useful:

* **Keyword alerts:** notify when a new cluster or signal matches keywords
* **Cluster recurrence alerts:** notify when a cluster crosses a threshold (ex: appears in 3+ distinct threads in a week)

Delivery channels: email + webhook.

### F) API

1. API keys per tenant with rotation and revocation.
2. Rate limits per plan.
3. Pagination, filtering, and time windows.

Proposed endpoints (example)

* `GET /v1/digests?from=YYYY-MM-DD&to=YYYY-MM-DD`
* `GET /v1/clusters?week=YYYY-MM-DD`
* `GET /v1/signals?subreddit=...&keyword=...`
* `POST /v1/webhooks/test`
* `POST /v1/source-sets` (configure sources)

---

## 7) Non-functional requirements

### Reliability

* Weekly digests must deliver on schedule with retries and failure reporting.
* A run produces immutable artifacts (digest content shouldn’t shift after delivery).

### Performance and cost

* Enforce plan caps and sampling strategy (ex: analyze top N posts per subreddit).
* Store LLM responses for auditability.
* Backpressure on Reddit fetching (you already have concurrency limits and retry patterns).

### Security and privacy

* Only public Reddit data; keep your current ethical stance prominent. ([GitHub][1])
* Protect API keys and user emails.
* Tenant isolation guarantees.
* Audit logs for key actions (login, key rotation, webhook deliveries).

---

## 8) What has to change from the current repo

### 8.1 Architecture: from single-user CLI to multi-tenant service

**Current:** local CLI, SQLite DB, FastAPI skeleton.
**Needed:** split into:

* **Core engine library** (keep most of `pain_radar/*` as reusable)
* **Service layer** (FastAPI app with auth, billing, API, UI)
* **Worker/scheduler** (background jobs for weekly runs and deliveries)

### 8.2 Storage: SQLite to multi-tenant database

SQLite is fine for local dev, but for paid SaaS you’ll want Postgres.

**New tables (high level)**

* `users`, `orgs`, `memberships`
* `plans`, `subscriptions`, `billing_events`
* `api_keys`
* `tenant_source_sets` (your preset + custom config)
* `runs` (tenant-scoped)
* `signals`, `clusters`, `digests` (tenant-scoped copies or references)
* `deliveries` (email/webhook/RSS delivery status)
* `alert_rules`, `alert_events`

### 8.3 Job orchestration

**Current:** user runs `pain-radar run` and `pain-radar digest`. ([GitHub][1])
**Needed:**

* scheduler triggers weekly runs per tenant
* worker executes pipeline with strict limits
* idempotency keys so re-runs don’t duplicate deliveries

### 8.4 Web app: from “public archive demo” to authenticated dashboard

**Needed UI pages (MVP)**

* Signup/login
* Billing page (manage subscription)
* Configure sources (choose preset + optional custom)
* Digest archive (list weeks, open digest, export)
* Alerts config
* API keys page (create/revoke, show usage)

### 8.5 Email + webhook infrastructure

* Add an email provider integration
* Add webhook delivery with signing secret + retries

### 8.6 Productization details

* Plan-based entitlements and enforcement
* Usage metering: posts fetched, posts analyzed, API calls
* Admin tooling: view tenants, rerun digest, inspect failures

### 8.7 Code quality and correctness fixes (before monetizing)

Based on your current code layout and snippets, there are a few “ship-stoppers” to address as part of the pivot:

* Align DB schema vs web features (the web alert form implies an `alerts` table; ensure schema and store layer match).
* Fix inconsistent variable naming in report generation and ensure `run_id` logic works end-to-end.
* Ensure the config and pipeline are consistent with the newer “source sets” approach (remove legacy references to old subreddit config paths).

---

## 9) MVP plan tiers (suggested)

* **Starter ($):** 1 source set, weekly email digest, web archive, limited history
* **Pro ($$):** multiple source sets, keyword alerts, webhook, “run now” (limited), longer history
* **Team ($$$):** org seats, shared configs, API access, higher caps

(Exact pricing is a later decision, but entitlements must exist in the data model from day one.)

---

## 10) Success metrics

* Activation: % who connect sources and successfully receive first digest
* Retention: weekly open rate + returning dashboard views
* Value: # digests read, # exports/copied, # API calls
* Cost: avg LLM spend per paying customer per week
* Churn and reasons (collect cancellation feedback)

---

## 11) Launch and rollout

1. **Phase 0:** keep CLI as “power user / dogfooding mode”
2. **Phase 1 (MVP SaaS):** paid weekly email digest + private archive
3. **Phase 2:** API + webhooks + alerts
4. **Phase 3:** team features + enterprise compliance polish

---

## 12) Open product decisions (make these explicit early)

* Is the subscription per **ICP bundle** (source set) or per **seat**?
* Do you sell “done-for-you digest curation” as a higher tier, or keep it fully automated?
* How much historical backfill do you allow on signup (it affects cost)?
* Will the API expose only tenant-generated artifacts, or also a global, anonymized “market index” later?

---

If you want, I can turn this into a repo-ready `docs/PRD_Pain_Radar_Pro.md` outline (including a concrete DB schema draft and API spec stubs) that matches your existing module boundaries, so implementing it becomes a set of PR-sized workstreams rather than one big rewrite.

[1]: https://github.com/albeorla/reddit-miner "GitHub - albeorla/reddit-miner: Mine Reddit for microSaaS and side-hustle ideas using AI. RSS-based (no API keys), GPT-powered extraction and scoring."
