schema = """
Tables:
- customers: customer_id (INTEGER, PK), segment (VARCHAR)
- products: product_card_id (INTEGER, PK), product_name (VARCHAR)
- orders: order_id (INTEGER, PK), customer_id (INTEGER, FK to customers), order_date (TIMESTAMP), market (VARCHAR)
- order_items: order_item_id (INTEGER, PK), order_id (INTEGER, FK to orders), product_card_id (INTEGER, FK to products), profit_per_order (FLOAT)
- shipping: shipping_id (INTEGER, PK), order_id (INTEGER, FK to orders), shipping_mode (VARCHAR), late_delivery_risk (INTEGER, 0 or 1 indicating risk)

Indexes:
- CREATE INDEX idx_orders_order_date ON orders (order_date);
- CREATE INDEX idx_orders_customer_id ON orders (customer_id);
- CREATE INDEX idx_order_items_order_id ON order_items (order_id);
- CREATE INDEX idx_order_items_product_card_id ON order_items (product_card_id);
- CREATE INDEX idx_shipping_order_id ON shipping (order_id);
"""

few_shot_examples = """
Example 1:
Question: What is the total number of orders per customer segment?
SQL: SELECT c.segment, COUNT(o.order_id) as order_count FROM orders o JOIN customers c ON o.customer_id = c.customer_id GROUP BY c.segment;

Example 2:
Question: Which products had the highest late delivery risk by market?
SQL: SELECT p.product_name, o.market, AVG(s.late_delivery_risk) as avg_late_risk FROM orders o JOIN order_items oi ON o.order_id = oi.order_id JOIN products p ON oi.product_card_id = p.product_card_id JOIN shipping s ON o.order_id = s.order_id GROUP BY p.product_name, o.market ORDER BY avg_late_risk DESC LIMIT 5;

Example 3:
Question: What is the total profit by customer segment across 2015 and 2016? only top 2 segments
SQL: SELECT c.segment, SUM(oi.profit_per_order) as total_profit FROM orders o JOIN customers c ON o.customer_id = c.customer_id JOIN order_items oi ON o.order_id = oi.order_id WHERE EXTRACT(YEAR FROM o.order_date) IN (2015, 2016) GROUP BY c.segment ORDER BY total_profit DESC LIMIT 2;

Example 4:
Question: Which shipping mode has the highest average late delivery risk for orders in LATAM in 2017?
SQL: SELECT s.shipping_mode, AVG(s.late_delivery_risk) as avg_late_risk FROM orders o JOIN shipping s ON o.order_id = s.order_id WHERE o.market = 'LATAM' AND EXTRACT(YEAR FROM o.order_date) = 2017 GROUP BY s.shipping_mode ORDER BY avg_late_risk DESC LIMIT 1;

Example 5:
Question: Who are our top 10 customers by total order value?
SQL: SELECT c.customer_id, SUM(oi.profit_per_order) as total_order_value FROM customers c JOIN orders o ON c.customer_id = o.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY c.customer_id ORDER BY total_order_value DESC LIMIT 10;

Example 6:
Question: What is the distribution of orders by customer segment and region?
SQL: SELECT c.segment, o.market as region, COUNT(o.order_id) as order_count FROM orders o JOIN customers c ON o.customer_id = c.customer_id GROUP BY c.segment, o.market;

Example 7:
Question: What was the total sales amount for the Southwest region in the last quarter?
SQL: SELECT SUM(oi.profit_per_order) as total_sales FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.market = 'Southwest' AND o.order_date >= (CURRENT_DATE - INTERVAL '3 months');

Example 8:
Question: Which shipping mode has the lowest rate of on-time deliveries?
SQL: SELECT s.shipping_mode, (1 - AVG(s.late_delivery_risk)) as on_time_delivery_rate FROM shipping s GROUP BY s.shipping_mode ORDER BY on_time_delivery_rate ASC LIMIT 1;

Example 9:
Question: What is the trend of late delivery risks over the years?
SQL: SELECT EXTRACT(YEAR FROM o.order_date) as year, AVG(s.late_delivery_risk) as avg_late_risk FROM orders o JOIN shipping s ON o.order_id = s.order_id GROUP BY EXTRACT(YEAR FROM o.order_date) ORDER BY year;
"""

ROLE_HIERARCHY = {
    "global_operations_manager": ["finance_manager", "planning_manager", "supply_chain_manager", "logistics_specialist", "supplier_manager"],
    "finance_manager": [],
    "planning_manager": ["supply_chain_manager", "logistics_specialist"],
    "supply_chain_manager": [],
    "logistics_specialist": [],
    "supplier_manager": []
}

USER_ROLES = {
    "supply_chain_manager": {
        "allowed_data": ["orders", "customers", "products", "shipping"],
        "allowed_regions": ["all"],
        "sensitive_data_access": False,
        "description": "Manages supply chain operations, no access to financial data."
    },
    "finance_manager": {
        "allowed_data": ["orders", "order_items"],
        "allowed_regions": ["all"],
        "sensitive_data_access": True,
        "description": "Access to financial data like profit and sales, restricted from operational data like shipping."
    },
    "planning_manager": {
        "allowed_data": ["orders", "products", "shipping"],
        "allowed_regions": ["all"],
        "sensitive_data_access": False,
        "description": "Access to inventory, logistics, and forecasting data for planning purposes."
    },
    "global_operations_manager": {
        "allowed_data": ["orders", "customers", "products", "shipping", "order_items"],
        "allowed_regions": ["all"],
        "sensitive_data_access": True,
        "description": "Oversees all operations with full data access."
    },
    "logistics_specialist": {
        "allowed_data": ["orders", "shipping"],
        "allowed_regions": ["all"],
        "sensitive_data_access": False,
        "description": "Focuses on logistics and shipping operations, no access to financial or product data."
    },
    "supplier_manager": {
        "allowed_data": ["products"],
        "allowed_regions": ["all"],
        "sensitive_data_access": False,
        "description": "Manages supplier relationships, restricted to product-related data."
    }
}

AUDIT_LOG_FILE = "audit_log.txt"