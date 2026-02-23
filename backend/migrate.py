import sqlite3
import os

db_path = "mdm_database.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE policies ADD COLUMN name VARCHAR DEFAULT 'Default Policy'")
        cur.execute("ALTER TABLE policies ADD COLUMN type VARCHAR DEFAULT 'security'")
        cur.execute("ALTER TABLE policies ADD COLUMN status VARCHAR DEFAULT 'applied'")
        conn.commit()
        print("Policies table altered successfully.")
    except Exception as e:
        print("Migration error policies (maybe columns exist?):", e)
        
    try:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY,
            device_id VARCHAR,
            type VARCHAR,
            message VARCHAR,
            severity VARCHAR DEFAULT 'info',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()
        print("Logs table created successfully.")
    except Exception as e:
        print("Migration error logs:", e)
        
    conn.close()
else:
    print("DB does not exist.")
