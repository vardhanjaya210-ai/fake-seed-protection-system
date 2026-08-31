import sqlite3

conn = sqlite3.connect('complaints.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product TEXT,
    dealer TEXT,
    description TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT UNIQUE,
    product_name TEXT,
    company TEXT,
    batch_no TEXT,
    status TEXT
)
''')

conn.commit()
conn.close()