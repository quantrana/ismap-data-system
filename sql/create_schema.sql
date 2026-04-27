-- ISMAP star schema for retail analytics on Istanbul shopping malls.
-- Run via `scripts/setup_database.py` (idempotent reset/create/verify/seed).

CREATE TABLE dim_time (
    date_key        INT PRIMARY KEY,              -- YYYYMMDD surrogate key, e.g. 20210305
    full_date       DATE NOT NULL,
    day_name        VARCHAR(10),                  -- e.g. "Friday"
    day_of_week     INT,                          -- 1=Monday .. 7=Sunday (ISO)
    week_number     INT,                          -- ISO week number
    month_number    INT,                          -- 1..12
    month_name      VARCHAR(10),                  -- e.g. "March"
    quarter         INT,                          -- 1..4
    year            INT,
    is_weekend      BOOLEAN DEFAULT FALSE,        -- TRUE for Saturday/Sunday
    is_holiday      BOOLEAN DEFAULT FALSE,        -- TRUE for Turkish public holidays (Nager.Date)
    season          VARCHAR(10)                   -- Winter / Spring / Summer / Autumn
);

COMMENT ON TABLE dim_time IS 'Date dimension with calendar attributes and Turkish public holiday flags.';

CREATE TABLE dim_customer (
    customer_key        SERIAL PRIMARY KEY,
    customer_id         VARCHAR(10) UNIQUE NOT NULL, -- natural key from source, e.g. "C241288"
    gender              VARCHAR(10),                 -- "Male" / "Female"
    age                 INT,                         -- 18..69 in source
    age_group           VARCHAR(10),                 -- e.g. "26-35"
    first_purchase_date DATE,
    last_purchase_date  DATE,
    total_transactions  INT DEFAULT 0
);

COMMENT ON TABLE dim_customer IS 'Customer dimension with demographics and lifecycle metrics.';

CREATE TABLE dim_product (
    product_key     SERIAL PRIMARY KEY,
    -- Categories: Books, Clothing, Cosmetics, Food & Beverage,
    --             Shoes, Souvenir, Technology, Toys.
    category        VARCHAR(50) UNIQUE NOT NULL
);

COMMENT ON TABLE dim_product IS 'Product dimension representing high-level product categories.';

CREATE TABLE dim_store (
    store_key       SERIAL PRIMARY KEY,
    shopping_mall   VARCHAR(100) UNIQUE NOT NULL    -- one of 10 Istanbul malls
);

COMMENT ON TABLE dim_store IS 'Store dimension representing Istanbul shopping malls.';

CREATE TABLE dim_payment (
    payment_key     SERIAL PRIMARY KEY,
    payment_method  VARCHAR(20) UNIQUE NOT NULL     -- Cash / Credit Card / Debit Card
);

COMMENT ON TABLE dim_payment IS 'Payment method dimension.';

CREATE TABLE fact_sales (
    sale_id         SERIAL PRIMARY KEY,
    invoice_no      VARCHAR(10) NOT NULL,           -- natural key from source, e.g. "I138884"
    date_key        INT NOT NULL REFERENCES dim_time(date_key),
    customer_key    INT NOT NULL REFERENCES dim_customer(customer_key),
    product_key     INT NOT NULL REFERENCES dim_product(product_key),
    store_key       INT NOT NULL REFERENCES dim_store(store_key),
    payment_key     INT NOT NULL REFERENCES dim_payment(payment_key),
    quantity        INT NOT NULL,
    price           DECIMAL(10,2) NOT NULL,         -- unit price in TRY
    total_amount    DECIMAL(12,2) NOT NULL,         -- quantity * price
    is_holiday      BOOLEAN DEFAULT FALSE,          -- denormalised from dim_time
    is_weekend      BOOLEAN DEFAULT FALSE           -- denormalised from dim_time
);

COMMENT ON TABLE fact_sales IS 'Transaction-level fact table for retail sales across Istanbul shopping malls.';

CREATE TABLE fact_daily_summary (
    summary_id              SERIAL PRIMARY KEY,
    date_key                INT NOT NULL REFERENCES dim_time(date_key),
    store_key               INT NOT NULL REFERENCES dim_store(store_key),
    total_revenue           DECIMAL(14,2),
    total_transactions      INT,
    avg_transaction_value   DECIMAL(10,2),
    unique_customers        INT,
    top_category            VARCHAR(50),
    top_payment_method      VARCHAR(20),
    UNIQUE(date_key, store_key)
);

COMMENT ON TABLE fact_daily_summary IS 'Daily aggregated metrics per store for reporting and dashboards.';

-- Foreign-key indexes to speed up dimension joins on fact tables.
CREATE INDEX idx_fact_sales_date     ON fact_sales(date_key);
CREATE INDEX idx_fact_sales_customer ON fact_sales(customer_key);
CREATE INDEX idx_fact_sales_product  ON fact_sales(product_key);
CREATE INDEX idx_fact_sales_store    ON fact_sales(store_key);
CREATE INDEX idx_fact_sales_payment  ON fact_sales(payment_key);
CREATE INDEX idx_fact_daily_date     ON fact_daily_summary(date_key);
CREATE INDEX idx_fact_daily_store    ON fact_daily_summary(store_key);
