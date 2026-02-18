"""Fix additional_image paths in database."""
import sqlite3

conn = sqlite3.connect('instance/orfe-shop.sqlite3')
c = conn.cursor()

# Check current state
c.execute("SELECT id, image FROM additional_image LIMIT 5")
print("Current additional images:")
for row in c.fetchall():
    print(f"  ID={row[0]}: {row[1]}")

# Fix additional images
c.execute("""
    UPDATE additional_image 
    SET image = 'static/uploads/' || image 
    WHERE image IS NOT NULL 
      AND image NOT LIKE 'static/%'
      AND image NOT LIKE 'http%'
""")
print(f"\nFixed {c.rowcount} additional images")

conn.commit()

# Verify product images too
c.execute("SELECT id, image FROM product LIMIT 5")
print("\nProduct images now:")
for row in c.fetchall():
    print(f"  ID={row[0]}: {row[1]}")

c.execute("SELECT id, image FROM additional_image LIMIT 5")
print("\nAdditional images now:")
for row in c.fetchall():
    print(f"  ID={row[0]}: {row[1]}")

conn.close()
print("\nDone!")
