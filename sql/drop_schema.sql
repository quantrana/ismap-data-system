-- Drop ISMAP star schema tables in reverse dependency order.

DROP TABLE IF EXISTS fact_daily_summary CASCADE;
DROP TABLE IF EXISTS fact_sales         CASCADE;
DROP TABLE IF EXISTS dim_payment        CASCADE;
DROP TABLE IF EXISTS dim_store          CASCADE;
DROP TABLE IF EXISTS dim_product        CASCADE;
DROP TABLE IF EXISTS dim_customer       CASCADE;
DROP TABLE IF EXISTS dim_time           CASCADE;
