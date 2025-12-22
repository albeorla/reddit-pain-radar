"""Multi-tenant SaaS database schema for Pain Radar Pro.

This module extends the base schema with tables for:
- Accounts & Auth (tenants, users, sessions, magic_links)
- Billing & Subscriptions (plans, subscriptions, billing_events)
- API Keys & Usage (api_keys, api_usage)
- Digests & Delivery (digests, deliveries, delivery_preferences)
- Alert Rules (alert_rules, alert_events)
- Job Scheduling (scheduled_jobs, job_executions)
- Audit Logging (audit_log)
"""

# =============================================================================
# ACCOUNTS & AUTH
# =============================================================================

TENANTS_TABLE = """
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
"""

USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    password_hash TEXT,
    role TEXT NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    CONSTRAINT valid_role CHECK (role IN ('owner', 'admin', 'member'))
);

CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""

SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
"""

MAGIC_LINKS_TABLE = """
CREATE TABLE IF NOT EXISTS magic_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# =============================================================================
# BILLING & SUBSCRIPTIONS
# =============================================================================

PLANS_TABLE = """
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price_monthly_cents INTEGER NOT NULL,
    price_annual_cents INTEGER NOT NULL,
    max_source_sets INTEGER NOT NULL DEFAULT 1,
    max_posts_per_week INTEGER NOT NULL DEFAULT 100,
    max_api_calls_per_day INTEGER NOT NULL DEFAULT 0,
    max_seats INTEGER NOT NULL DEFAULT 1,
    features JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

PLANS_SEED = """
INSERT INTO plans (id, name, price_monthly_cents, price_annual_cents, max_source_sets, max_posts_per_week, max_api_calls_per_day, max_seats, features)
VALUES
    ('starter', 'Starter', 1900, 19000, 1, 100, 0, 1, '["email_digest", "web_archive"]'),
    ('pro', 'Pro', 4900, 49000, 5, 500, 1000, 1, '["email_digest", "web_archive", "webhook", "run_now", "keyword_alerts"]'),
    ('team', 'Team', 9900, 99000, 20, 2000, 10000, 5, '["email_digest", "web_archive", "webhook", "run_now", "keyword_alerts", "api"]')
ON CONFLICT (id) DO NOTHING;
"""

SUBSCRIPTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES plans(id),
    stripe_subscription_id TEXT UNIQUE,
    stripe_customer_id TEXT,
    status TEXT NOT NULL DEFAULT 'trialing',
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT valid_status CHECK (status IN ('trialing', 'active', 'past_due', 'canceled', 'paused'))
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant ON subscriptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe ON subscriptions(stripe_subscription_id);
"""

BILLING_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS billing_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    stripe_event_id TEXT UNIQUE,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_billing_events_tenant ON billing_events(tenant_id);
"""

# =============================================================================
# API KEYS
# =============================================================================

API_KEYS_TABLE = """
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    scopes JSONB NOT NULL DEFAULT '["read"]',
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
"""

API_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS api_usage (
    id BIGSERIAL PRIMARY KEY,
    api_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    response_time_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_usage_key ON api_usage(api_key_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage(created_at);
"""

# =============================================================================
# DIGESTS & DELIVERY
# =============================================================================

DIGESTS_TABLE = """
CREATE TABLE IF NOT EXISTS digests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    run_id INTEGER,
    week_start DATE NOT NULL,
    title TEXT NOT NULL,
    content_markdown TEXT NOT NULL,
    content_html TEXT NOT NULL,
    content_json JSONB NOT NULL,
    cluster_count INTEGER NOT NULL DEFAULT 0,
    signal_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_digests_tenant ON digests(tenant_id);
CREATE INDEX IF NOT EXISTS idx_digests_week ON digests(tenant_id, week_start);
"""

DELIVERIES_TABLE = """
CREATE TABLE IF NOT EXISTS deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    digest_id UUID REFERENCES digests(id) ON DELETE SET NULL,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT valid_channel CHECK (channel IN ('email', 'webhook', 'rss')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'sent', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_deliveries_tenant ON deliveries(tenant_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_status ON deliveries(status);
"""

DELIVERY_PREFERENCES_TABLE = """
CREATE TABLE IF NOT EXISTS delivery_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE(tenant_id, channel)
);
"""

# =============================================================================
# ALERT RULES
# =============================================================================

ALERT_RULES_TABLE = """
CREATE TABLE IF NOT EXISTS alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    config JSONB NOT NULL,
    delivery_channels JSONB NOT NULL DEFAULT '["email"]',
    is_active BOOLEAN DEFAULT TRUE,
    last_triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT valid_rule_type CHECK (rule_type IN ('keyword', 'cluster_recurrence'))
);

CREATE INDEX IF NOT EXISTS idx_alert_rules_tenant ON alert_rules(tenant_id);
"""

ALERT_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS alert_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    rule_id UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    signal_id INTEGER,
    cluster_id TEXT,
    matched_value TEXT,
    notified BOOLEAN DEFAULT FALSE,
    notified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_events_rule ON alert_events(rule_id);
"""

# =============================================================================
# JOB SCHEDULING
# =============================================================================

SCHEDULED_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    schedule_cron TEXT NOT NULL DEFAULT '0 9 * * 1',
    config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_tenant ON scheduled_jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_next ON scheduled_jobs(next_run_at);
"""

JOB_EXECUTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS job_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES scheduled_jobs(id) ON DELETE SET NULL,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_executions_tenant ON job_executions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_job_executions_status ON job_executions(status);
"""

# =============================================================================
# AUDIT LOG
# =============================================================================

AUDIT_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    metadata JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
"""

# =============================================================================
# TENANT ISOLATION MIGRATIONS
# =============================================================================

TENANT_ISOLATION_MIGRATIONS = """
-- Add tenant_id to existing tables (run as Alembic migration)
-- Note: These are ALTER statements for existing tables

-- ALTER TABLE source_sets ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
-- ALTER TABLE runs ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
-- ALTER TABLE posts ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
-- ALTER TABLE signals ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
-- ALTER TABLE clusters ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
-- ALTER TABLE watchlists ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
-- ALTER TABLE alerts ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
-- ALTER TABLE alert_matches ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;

-- CREATE INDEX IF NOT EXISTS idx_source_sets_tenant ON source_sets(tenant_id);
-- CREATE INDEX IF NOT EXISTS idx_runs_tenant ON runs(tenant_id);
-- CREATE INDEX IF NOT EXISTS idx_posts_tenant ON posts(tenant_id);
-- CREATE INDEX IF NOT EXISTS idx_signals_tenant ON signals(tenant_id);
-- CREATE INDEX IF NOT EXISTS idx_clusters_tenant ON clusters(tenant_id);
-- CREATE INDEX IF NOT EXISTS idx_watchlists_tenant ON watchlists(tenant_id);
"""

# =============================================================================
# SCHEMA ASSEMBLY
# =============================================================================

SAAS_SCHEMA = "\n".join(
    [
        "-- Pain Radar Pro: Multi-Tenant SaaS Schema",
        "-- Generated for Postgres",
        "",
        "-- ACCOUNTS & AUTH",
        TENANTS_TABLE,
        USERS_TABLE,
        SESSIONS_TABLE,
        MAGIC_LINKS_TABLE,
        "",
        "-- BILLING & SUBSCRIPTIONS",
        PLANS_TABLE,
        PLANS_SEED,
        SUBSCRIPTIONS_TABLE,
        BILLING_EVENTS_TABLE,
        "",
        "-- API KEYS",
        API_KEYS_TABLE,
        API_USAGE_TABLE,
        "",
        "-- DIGESTS & DELIVERY",
        DIGESTS_TABLE,
        DELIVERIES_TABLE,
        DELIVERY_PREFERENCES_TABLE,
        "",
        "-- ALERT RULES",
        ALERT_RULES_TABLE,
        ALERT_EVENTS_TABLE,
        "",
        "-- JOB SCHEDULING",
        SCHEDULED_JOBS_TABLE,
        JOB_EXECUTIONS_TABLE,
        "",
        "-- AUDIT LOG",
        AUDIT_LOG_TABLE,
    ]
)


def get_saas_schema() -> str:
    """Get the complete SaaS schema SQL."""
    return SAAS_SCHEMA


def get_migration_sql() -> str:
    """Get SQL for migrating existing tables to multi-tenant."""
    return TENANT_ISOLATION_MIGRATIONS
