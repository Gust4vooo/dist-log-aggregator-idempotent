CREATE TABLE IF NOT EXISTS processed_events (
    topic       VARCHAR(255) NOT NULL,
    event_id    VARCHAR(255) NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL,
    source      VARCHAR(255),
    payload     JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (topic, event_id)
);

CREATE TABLE IF NOT EXISTS audit_stats (
    metric_key VARCHAR(50) PRIMARY KEY,
    counter    BIGINT DEFAULT 0
);

INSERT INTO audit_stats (metric_key, counter) VALUES 
    ('duplicates_dropped', 0)
ON CONFLICT DO NOTHING;