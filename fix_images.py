"""Fix image paths in database - prepend static/uploads/ where missing."""
import sqlite3

conn = sqlite3.connect('instance/orfe-shop.sqlite3')
c = conn.cursor()

# Show current state
c.execute("SELECT id, image FROM product LIMIT 5")
print("Current product images:")
for row in c.fetchall():
    print(f"  ID={row[0]}: {row[1]}")

# Fix product images
c.execute("""
    UPDATE product 
    SET image = 'static/uploads/' || image 
    WHERE image IS NOT NULL 
      AND image != 'default.jpg' 
      AND image NOT LIKE 'static/%'
      AND image NOT LIKE 'http%'
""")
print(f"\nFixed {c.rowcount} product images")

# Fix additional images 
c.execute("""
    UPDATE additional_image 
    SET image_path = 'static/uploads/' || image_path 
    WHERE image_path IS NOT NULL 
      AND image_path NOT LIKE 'static/%'
      AND image_path NOT LIKE 'http%'
""")
print(f"Fixed {c.rowcount} additional images")

conn.commit()

# Verify
c.execute("SELECT id, image FROM product LIMIT 5")
print("\nAfter fix:")
for row in c.fetchall():
    print(f"  ID={row[0]}: {row[1]}")

conn.close()
print("\nDone!")
