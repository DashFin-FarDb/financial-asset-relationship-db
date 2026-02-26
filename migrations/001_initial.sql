-- Schema defining assets, relationships, and regulatory events

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    sector TEXT NOT NULL,
    price REAL NOT NULL,
    market_cap REAL,
    currency TEXT NOT NULL,
    pe_ratio REAL,
    dividend_yield REAL,
    earnings_per_share REAL,
    book_value REAL,
    yield_to_maturity REAL,
    coupon_rate REAL,
    maturity_date TEXT,
    credit_rating TEXT,
    issuer_id TEXT,
    contract_size REAL,
    delivery_date TEXT,
    volatility REAL,
    exchange_rate REAL,
    country TEXT,
    central_bank_rate REAL
);

CREATE TABLE IF NOT EXISTS asset_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_asset_id TEXT NOT NULL,
    target_asset_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    strength REAL NOT NULL,
    bidirectional INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT fk_relationship_source FOREIGN KEY (source_asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    CONSTRAINT fk_relationship_target FOREIGN KEY (target_asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    CONSTRAINT uq_relationship UNIQUE (source_asset_id, target_asset_id, relationship_type)
);

CREATE TABLE IF NOT EXISTS regulatory_events (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    impact_score REAL NOT NULL,
    CONSTRAINT fk_event_asset FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS regulatory_event_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    CONSTRAINT fk_event FOREIGN KEY (event_id) REFERENCES regulatory_events(id) ON DELETE CASCADE,
    CONSTRAINT fk_related_asset FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    CONSTRAINT uq_event_asset UNIQUE (event_id, asset_id)
);
