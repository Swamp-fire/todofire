import sqlite3
import datetime
from task_model import Task # Assuming task_model.py is in the same directory

DB_NAME = "tasks.db"

def create_connection(db_file_name=DB_NAME):
    conn = None
    try:
        conn = sqlite3.connect(db_file_name)
    except sqlite3.Error as e:
        print(f"Error connecting to database {db_file_name}: {e}")
    return conn

def create_table(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            duration INTEGER,
            creation_date TEXT NOT NULL,
            repetition TEXT,
            priority INTEGER,
            category TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'Pending',
            last_reset_date TEXT
        );
        """)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating Tasks table: {e}")

def add_task(conn, task: Task):
    sql = ''' INSERT INTO Tasks(title, description, duration, creation_date, repetition, priority, category, due_date, status, last_reset_date)
              VALUES(?,?,?,?,?,?,?,?,?,?) '''
    cursor = conn.cursor()
    try:
        # Ensure last_reset_date has a value (task model constructor handles default to today if None)
        current_last_reset_date = task.last_reset_date if task.last_reset_date is not None else datetime.date.today().isoformat()

        cursor.execute(sql, (task.title, task.description, task.duration, task.creation_date,
                              task.repetition, task.priority, task.category, task.due_date,
                              task.status, current_last_reset_date))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error adding task: {e}")
        return None

def get_task(conn, task_id: int):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM Tasks WHERE id=?", (task_id,))
        row = cursor.fetchone()
        if row:
            return Task(id=row[0], title=row[1], description=row[2], duration=row[3],
                        creation_date=row[4], repetition=row[5], priority=row[6], category=row[7],
                        due_date=row[8], status=row[9], last_reset_date=row[10])
        return None
    except sqlite3.Error as e:
        print(f"Error getting task {task_id}: {e}")
        return None

def get_all_tasks(conn):
    tasks = []
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM Tasks ORDER BY creation_date DESC")
        rows = cursor.fetchall()
        for row in rows:
            tasks.append(Task(id=row[0], title=row[1], description=row[2], duration=row[3],
                              creation_date=row[4], repetition=row[5], priority=row[6], category=row[7],
                              due_date=row[8], status=row[9], last_reset_date=row[10]))
    except sqlite3.Error as e:
        print(f"Error getting all tasks: {e}")
    return tasks

def update_task(conn, task: Task):
    sql = ''' UPDATE Tasks
              SET title = ?,
                  description = ?,
                  duration = ?,
                  creation_date = ?,
                  repetition = ?,
                  priority = ?,
                  category = ?,
                  due_date = ?,
                  status = ?,
                  last_reset_date = ?
              WHERE id = ? '''
    cursor = conn.cursor()
    try:
        # Ensure last_reset_date has a value
        current_last_reset_date = task.last_reset_date if task.last_reset_date is not None else datetime.date.today().isoformat()

        cursor.execute(sql, (task.title, task.description, task.duration, task.creation_date,
                              task.repetition, task.priority, task.category, task.due_date,
                              task.status, current_last_reset_date, task.id))
        conn.commit()
        return cursor.rowcount > 0 # Return True if a row was actually updated
    except sqlite3.Error as e:
        print(f"Error updating task {task.id}: {e}")
        return False

def delete_task(conn, task_id: int):
    sql = 'DELETE FROM Tasks WHERE id=?'
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (task_id,))
        conn.commit()
        return cursor.rowcount > 0 # Return True if a row was actually deleted
    except sqlite3.Error as e:
        print(f"Error deleting task {task_id}: {e}")
        return False

if __name__ == '__main__':
    # Example Usage (for testing this module directly)
    print("Database Manager Module Direct Test")
    db_conn = create_connection()
    if db_conn:
        create_table(db_conn) # Ensure table exists

        # Example: Add a task
        # Note: Task model's __init__ handles default for last_reset_date
        sample_task_data = {
            "id": 0, "title": "Test DB Task", "description": "Testing DB.",
            "duration": 60, "creation_date": datetime.datetime.now().isoformat(),
            "repetition": "Daily", "priority": 1, "category": "Test",
            "due_date": (datetime.datetime.now() + datetime.timedelta(days=1)).isoformat(),
            "status": "Pending"
            # last_reset_date will be defaulted by Task constructor
        }
        # For add_task, ID in the object is usually ignored by DB if PK is autoincrement.
        # So, passing id=0 or id=None is fine. Task model expects an int.
        test_task = Task(**sample_task_data)

        task_id = add_task(db_conn, test_task)
        if task_id:
            print(f"Added task with ID: {task_id}")

            retrieved_task = get_task(db_conn, task_id)
            if retrieved_task:
                print(f"Retrieved task: {retrieved_task.title}, Due: {retrieved_task.due_date}, Status: {retrieved_task.status}, Last Reset: {retrieved_task.last_reset_date}")

            retrieved_task.status = "Completed"
            # Test update with a None due_date
            retrieved_task.due_date = None
            if update_task(db_conn, retrieved_task):
                print(f"Updated task {task_id}")
                updated_retrieved_task = get_task(db_conn, task_id)
                if updated_retrieved_task:
                     print(f"After update: {updated_retrieved_task.title}, Due: {updated_retrieved_task.due_date}, Status: {updated_retrieved_task.status}")

            all_tasks = get_all_tasks(db_conn)
            print(f"Total tasks: {len(all_tasks)}")
            for t in all_tasks:
                print(f"- {t.title} (ID: {t.id}, Status: {t.status}, Due: {t.due_date})")

            # if delete_task(db_conn, task_id):
            #     print(f"Deleted task {task_id}")

        db_conn.close()
    else:
        print("Failed to connect to the database.")
