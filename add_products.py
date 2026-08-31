import sqlite3

conn = sqlite3.connect('complaints.db')
cursor = conn.cursor()

products = [
    ('FS001', 'Paddy Seeds', 'ABC Seeds', 'B101', 'Genuine'),
    ('FS002', 'Groundnut Seeds', 'Green Agro', 'B202', 'Genuine'),
    ('FERT001', 'Urea Fertilizer', 'Agro India', 'U301', 'Genuine')
]

cursor.executemany('''
    INSERT OR IGNORE INTO products
    (product_id, product_name, company, batch_no, status)
    VALUES (?, ?, ?, ?, ?)
''', products)

conn.commit()
conn.close()

print("Products added successfully!")