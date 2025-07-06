import sqlite3

# Connect to the SQLite DB
conn = sqlite3.connect("instance/users.db")
cursor = conn.cursor()

# View all tasks
cursor.execute("SELECT * FROM task")
tasks = cursor.fetchall()

print("📋 All tasks in the database:\n")
for task in tasks:
    print(task)

conn.close()
