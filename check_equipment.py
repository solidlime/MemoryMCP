import sqlite3

conn = sqlite3.connect('memory/nilou/inventory.sqlite')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute('''
    SELECT i.item_name, inv.equipped_slot, inv.is_equipped
    FROM inventory inv
    JOIN items i ON inv.item_id = i.item_id
    WHERE inv.persona = 'nilou' AND inv.is_equipped = 1
''')

rows = cursor.fetchall()

if rows:
    print("現在装備中のアイテム:")
    for row in rows:
        print(f"  {row['equipped_slot']}: {row['item_name']}")
else:
    print("装備中のアイテムなし")

conn.close()
