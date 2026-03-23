import sqlite3

conn = sqlite3.connect("sample.db")
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS orders")
cur.execute("DROP TABLE IF EXISTS customers")

cur.execute("""
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name TEXT,
    region TEXT
)
""")

cur.execute("""
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date TEXT,
    revenue REAL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
)
""")

customers = [
    (1, "Alice", "East"),
    (2, "Bob", "West"),
    (3, "Charlie", "North"),
    (4, "David", "South")
]

orders = [
    (101, 1, "2026-01-10", 1200.0),
    (102, 2, "2026-01-12", 800.0),
    (103, 1, "2026-02-01", 1500.0),
    (104, 3, "2026-02-15", 600.0),
    (105, 4, "2026-02-20", 900.0),
    (106, 2, "2026-03-01", 1300.0)
]

cur.executemany("INSERT INTO customers VALUES (?, ?, ?)", customers)
cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", orders)

conn.commit()
conn.close()

print("sample.db created successfully")