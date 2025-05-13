-- corec_emergente/plugins/trading/sql/trading_db.sql
-- Esquema de base de datos para el plugin de trading

CREATE TABLE users (
    usuario_id VARCHAR(50) PRIMARY KEY,
    capital_inicial FLOAT NOT NULL,
    capital_disponible FLOAT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    timestamp TIMESTAMP NOT NULL
);
CREATE INDEX idx_users_status ON users(status);

CREATE TABLE capital_pool (
    usuario_id VARCHAR(50) PRIMARY KEY,
    capital_inicial FLOAT NOT NULL,
    capital_disponible FLOAT NOT NULL,
    ganancia_shadow FLOAT DEFAULT 0.0,
    porcentaje_participacion FLOAT DEFAULT 0.0,
    timestamp TIMESTAMP NOT NULL
);
CREATE INDEX idx_capital_pool_timestamp ON capital_pool(timestamp);

CREATE TABLE daily_metrics (
    id SERIAL PRIMARY KEY,
    total_capital FLOAT NOT NULL,
    active_capital FLOAT NOT NULL,
    users_count INTEGER NOT NULL,
    trades_count INTEGER NOT NULL,
    win_rate FLOAT DEFAULT 0.0,
    profit_factor FLOAT DEFAULT 0.0,
    max_consecutive_losses INTEGER DEFAULT 0,
    timestamp TIMESTAMP NOT NULL
);
CREATE INDEX idx_daily_metrics_timestamp ON daily_metrics(timestamp);

CREATE TABLE strategy_decisions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    modo VARCHAR(20) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    decision_type VARCHAR(20),
    price FLOAT,
    probability FLOAT,
    outcome FLOAT,
    volatility FLOAT,
    volume FLOAT,
    timestamp TIMESTAMP NOT NULL
);
CREATE INDEX idx_strategy_decisions_timestamp ON strategy_decisions(timestamp);

CREATE TABLE macro_metrics (
    id SERIAL PRIMARY KEY,
    sp500_price FLOAT,
    nasdaq_price FLOAT,
    dxy_price FLOAT,
    gold_price FLOAT,
    oil_price FLOAT,
    btc_market_cap FLOAT,
    eth_market_cap FLOAT,
    altcoins_volume FLOAT,
    news_sentiment FLOAT,
    timestamp TIMESTAMP NOT NULL
);
CREATE INDEX idx_macro_metrics_timestamp ON macro_metrics(timestamp);
