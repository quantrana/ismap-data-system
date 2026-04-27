-- Reference analytical queries against the ISMAP star schema.

-- Q1: Total revenue by shopping mall.
SELECT
    s.shopping_mall,
    SUM(f.total_amount) AS total_revenue
FROM fact_sales f
JOIN dim_store s ON f.store_key = s.store_key
GROUP BY s.shopping_mall
ORDER BY total_revenue DESC;

-- Q2: Top 5 product categories by total revenue.
SELECT
    p.category,
    SUM(f.total_amount) AS total_revenue
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.category
ORDER BY total_revenue DESC
LIMIT 5;

-- Q3: Monthly revenue trend.
SELECT
    t.year,
    t.month_number AS month,
    SUM(f.total_amount) AS total_revenue
FROM fact_sales f
JOIN dim_time t ON f.date_key = t.date_key
GROUP BY t.year, t.month_number
ORDER BY t.year, t.month_number;

-- Q4: Holiday vs non-holiday average transaction value.
SELECT
    t.is_holiday,
    AVG(f.total_amount) AS avg_transaction_value
FROM fact_sales f
JOIN dim_time t ON f.date_key = t.date_key
GROUP BY t.is_holiday
ORDER BY t.is_holiday DESC;

-- Q5: Customer count by age group and gender.
SELECT
    c.age_group,
    c.gender,
    COUNT(DISTINCT c.customer_key) AS customer_count
FROM dim_customer c
JOIN fact_sales f ON f.customer_key = c.customer_key
GROUP BY c.age_group, c.gender
ORDER BY c.age_group, c.gender;

-- Q6: Payment method distribution by mall.
SELECT
    s.shopping_mall,
    pay.payment_method,
    COUNT(*) AS transaction_count,
    SUM(f.total_amount) AS total_revenue
FROM fact_sales f
JOIN dim_store s   ON f.store_key   = s.store_key
JOIN dim_payment pay ON f.payment_key = pay.payment_key
GROUP BY s.shopping_mall, pay.payment_method
ORDER BY s.shopping_mall, transaction_count DESC;

-- Q7: Weekend vs weekday total revenue.
SELECT
    t.is_weekend,
    SUM(f.total_amount) AS total_revenue
FROM fact_sales f
JOIN dim_time t ON f.date_key = t.date_key
GROUP BY t.is_weekend
ORDER BY t.is_weekend DESC;

-- Q8: Seasonal revenue breakdown.
SELECT
    t.season,
    SUM(f.total_amount) AS total_revenue
FROM fact_sales f
JOIN dim_time t ON f.date_key = t.date_key
GROUP BY t.season
ORDER BY total_revenue DESC;

-- Q9: Top 10 customers by total spending.
SELECT
    c.customer_id,
    c.age_group,
    c.gender,
    SUM(f.total_amount) AS total_spent
FROM fact_sales f
JOIN dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.customer_id, c.age_group, c.gender
ORDER BY total_spent DESC
LIMIT 10;

-- Q10: Daily summary for a specific mall (replace :mall_name).
SELECT
    t.full_date,
    s.shopping_mall,
    ds.total_revenue,
    ds.total_transactions,
    ds.avg_transaction_value,
    ds.unique_customers,
    ds.top_category,
    ds.top_payment_method
FROM fact_daily_summary ds
JOIN dim_time  t ON ds.date_key  = t.date_key
JOIN dim_store s ON ds.store_key = s.store_key
WHERE s.shopping_mall = :mall_name
ORDER BY t.full_date;
