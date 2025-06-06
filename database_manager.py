import sqlite3
import datetime
from task_model import Task # Assuming task_model.py is in the same directory

DB_NAME = "tasks.db"

def create_connection(db_file_name=DB_NAME):
    conn = None
    try:
        conn = sqlite3.connect(db_file_name)
    except sqlite3.Error as e:
        print(f"Error connecting to database {db_file_name}: {e}") # Existing print
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
        print(f"Error creating Tasks table: {e}") # Existing print

def add_task(conn, task: Task):
    sql = ''' INSERT INTO Tasks(title, description, duration, creation_date, repetition, priority, category, due_date, status, last_reset_date)
              VALUES(?,?,?,?,?,?,?,?,?,?) '''
    cursor = conn.cursor()
    try:
        current_last_reset_date = task.last_reset_date if task.last_reset_date is not None else datetime.date.today().isoformat()
        cursor.execute(sql, (task.title, task.description, task.duration, task.creation_date,
                              task.repetition, task.priority, task.category, task.due_date,
                              task.status, current_last_reset_date))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error adding task: {e}") # Existing print
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
        print(f"Error getting task {task_id}: {e}") # Existing print
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
        print(f"Error getting all tasks: {e}") # Existing print
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
        current_last_reset_date = task.last_reset_date if task.last_reset_date is not None else datetime.date.today().isoformat()
        cursor.execute(sql, (task.title, task.description, task.duration, task.creation_date,
                              task.repetition, task.priority, task.category, task.due_date,
                              task.status, current_last_reset_date, task.id))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error updating task {task.id}: {e}") # Existing print
        return False

def delete_task(conn, task_id: int):
    sql = 'DELETE FROM Tasks WHERE id=?'
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (task_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error deleting task {task_id}: {e}") # Existing print
        return False

def check_timeslot_overlap(start_dt1: datetime.datetime, end_dt1: datetime.datetime,
                              start_dt2: datetime.datetime, end_dt2: datetime.datetime) -> bool:
    """
    Checks if two time intervals [start_dt1, end_dt1) and [start_dt2, end_dt2) overlap.
    The end of the interval is considered exclusive.
    Returns True if they overlap, False otherwise.
    Also returns False if any input is not a datetime object or if an interval is invalid (start >= end).
    """
    if not (isinstance(start_dt1, datetime.datetime) and
            isinstance(end_dt1, datetime.datetime) and
            isinstance(start_dt2, datetime.datetime) and
            isinstance(end_dt2, datetime.datetime)):
        print(f"Warning: Non-datetime type passed to check_timeslot_overlap. Types: {type(start_dt1)}, {type(end_dt1)}, {type(start_dt2)}, {type(end_dt2)}")
        return False

    if start_dt1 >= end_dt1 or start_dt2 >= end_dt2:
        print(f"Warning: Invalid time interval provided to check_timeslot_overlap. S1-E1: {start_dt1}-{end_dt1}, S2-E2: {start_dt2}-{end_dt2}")
        return False

    return max(start_dt1, start_dt2) < min(end_dt1, end_dt2)

if __name__ == '__main__':
    print("Database Manager Module Direct Test")
    db_conn = create_connection()
    if db_conn:
        create_table(db_conn)

        sample_task_data = {
            "id": 0, "title": "Test DB Task", "description": "Testing DB.",
            "duration": 60, "creation_date": datetime.datetime.now().isoformat(),
            "repetition": "Daily", "priority": 1, "category": "Test",
            "due_date": (datetime.datetime.now() + datetime.timedelta(days=1)).isoformat(),
            "status": "Pending"
        }
        test_task = Task(**sample_task_data)

        task_id = add_task(db_conn, test_task)
        if task_id:
            print(f"Added task with ID: {task_id}")
            retrieved_task = get_task(db_conn, task_id)
            if retrieved_task:
                print(f"Retrieved task: {retrieved_task.title}, Due: {retrieved_task.due_date}, Status: {retrieved_task.status}, Last Reset: {retrieved_task.last_reset_date}")
            retrieved_task.status = "Completed"
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

        # Test overlap function
        print("\nTesting timeslot overlap function:")
        dt1_start = datetime.datetime(2024, 1, 1, 10, 0, 0)
        dt1_end   = datetime.datetime(2024, 1, 1, 11, 0, 0)
        dt2_start = datetime.datetime(2024, 1, 1, 10, 30, 0) # Overlaps
        dt2_end   = datetime.datetime(2024, 1, 1, 11, 30, 0)
        dt3_start = datetime.datetime(2024, 1, 1, 12, 0, 0) # No overlap
        dt3_end   = datetime.datetime(2024, 1, 1, 13, 0, 0)
        dt4_start = datetime.datetime(2024, 1, 1, 9, 0, 0)  # Contains dt1
        dt4_end   = datetime.datetime(2024, 1, 1, 12, 0, 0)
        dt5_start = datetime.datetime(2024, 1, 1, 10, 0, 0) # Exact same
        dt5_end   = datetime.datetime(2024, 1, 1, 11, 0, 0)
        dt6_start = datetime.datetime(2024, 1, 1, 11, 0, 0) # Adjacent (touching, not overlapping)
        dt6_end   = datetime.datetime(2024, 1, 1, 12, 0, 0)


        print(f"Interval 1: {dt1_start} - {dt1_end}")
        print(f"Interval 2 (overlaps): {dt2_start} - {dt2_end} -> Overlap? {check_timeslot_overlap(dt1_start, dt1_end, dt2_start, dt2_end)}") # True
        print(f"Interval 3 (no overlap): {dt3_start} - {dt3_end} -> Overlap? {check_timeslot_overlap(dt1_start, dt1_end, dt3_start, dt3_end)}") # False
        print(f"Interval 4 (contains 1): {dt4_start} - {dt4_end} -> Overlap? {check_timeslot_overlap(dt1_start, dt1_end, dt4_start, dt4_end)}") # True
        print(f"Interval 5 (same as 1): {dt5_start} - {dt5_end} -> Overlap? {check_timeslot_overlap(dt1_start, dt1_end, dt5_start, dt5_end)}") # True
        print(f"Interval 6 (adjacent to 1): {dt6_start} - {dt6_end} -> Overlap? {check_timeslot_overlap(dt1_start, dt1_end, dt6_start, dt6_end)}") # False
        print(f"Invalid interval (end before start): Overlap? {check_timeslot_overlap(dt1_end, dt1_start, dt2_start, dt2_end)}") # False
        print(f"Non-datetime input: Overlap? {check_timeslot_overlap(dt1_start, dt1_end, 'not-a-datetime', dt2_end)}") # False


        db_conn.close()
    else:
        print("Failed to connect to the database.")
