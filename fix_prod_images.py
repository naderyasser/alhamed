import sqlite3
conn = sqlite3.connect('instance/orfe-shop.sqlite3')
c = conn.cursor()
c.execute("UPDATE product SET image = 'static/uploads/' || image WHERE image IS NOT NULL AND image != 'default.jpg' AND image NOT LIKE 'static/%' AND image NOT LIKE 'http%'")
print(f"Fixed {c.rowcount} product images")
conn.commit()
c.execute("SELECT id, image FROM product LIMIT 5")
for r in c.fetchall():
    print(f"  ID={r[0]}: {r[1]}")
conn.close()
