import sqlite3
import datetime
from datetime import time # Ensure time is available for type hinting and usage
from task_model import Task

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
        current_last_reset_date = task.last_reset_date if task.last_reset_date is not None else datetime.date.today().isoformat()
        cursor.execute(sql, (task.title, task.description, task.duration, task.creation_date,
                              task.repetition, task.priority, task.category, task.due_date,
                              task.status, current_last_reset_date, task.id))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error updating task {task.id}: {e}")
        return False

def delete_task(conn, task_id: int):
    sql = 'DELETE FROM Tasks WHERE id=?'
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (task_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error deleting task {task_id}: {e}")
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
        print(f"Warning (check_timeslot_overlap): Non-datetime type passed. Types: {type(start_dt1)}, {type(end_dt1)}, {type(start_dt2)}, {type(end_dt2)}")
        return False

    if start_dt1 >= end_dt1 or start_dt2 >= end_dt2:
        print(f"Warning (check_timeslot_overlap): Invalid time interval. S1-E1: {start_dt1}-{end_dt1}, S2-E2: {start_dt2}-{end_dt2}")
        return False

    return max(start_dt1, start_dt2) < min(end_dt1, end_dt2)

def check_time_only_overlap(start_time1: time, end_time1: time,
                               start_time2: time, end_time2: time) -> bool:
    """
    Checks if two time-of-day intervals [start_time1, end_time1) and
    [start_time2, end_time2) overlap. Assumes times are on the same conceptual day.
    IMPORTANT: This function expects end_time > start_time for each interval.
    It does NOT handle cases where an interval inherently crosses midnight by passing
    time objects like (22:00, 02:00) where end_time < start_time.
    The logic in main_app.py must account for midnight crossings by potentially
    splitting intervals or projecting them onto comparable date contexts if needed,
    before calling this function with adjusted time segments or using check_timeslot_overlap.
    The end of the interval is considered exclusive.
    Returns True if they overlap, False otherwise.
    """
    if not (isinstance(start_time1, time) and
            isinstance(end_time1, time) and
            isinstance(start_time2, time) and
            isinstance(end_time2, time)):
        print(f"Warning (check_time_only_overlap): Non-datetime.time type passed. Types: {type(start_time1)}, {type(end_time1)}, {type(start_time2)}, {type(end_time2)}")
        return False

    if start_time1 >= end_time1 or start_time2 >= end_time2:
        print(f"Warning (check_time_only_overlap): Invalid time interval (start_time >= end_time): "
              f"{start_time1}-{end_time1} or {start_time2}-{end_time2}")
        return False

    return max(start_time1, start_time2) < min(end_time1, end_time2)


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
        # ... (rest of existing __main__ test code) ...
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
            for t_item in all_tasks: # renamed t to t_item to avoid conflict with datetime.time
                print(f"- {t_item.title} (ID: {t_item.id}, Status: {t_item.status}, Due: {t_item.due_date})")

        print("\nTesting timeslot overlap function:")
        dt1_start = datetime.datetime(2024, 1, 1, 10, 0, 0)
        dt1_end   = datetime.datetime(2024, 1, 1, 11, 0, 0)
        dt2_start = datetime.datetime(2024, 1, 1, 10, 30, 0)
        dt2_end   = datetime.datetime(2024, 1, 1, 11, 30, 0)
        dt3_start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        dt3_end   = datetime.datetime(2024, 1, 1, 13, 0, 0)
        print(f"DT Overlap 1: {check_timeslot_overlap(dt1_start, dt1_end, dt2_start, dt2_end)}") # True
        print(f"DT No Overlap 1: {check_timeslot_overlap(dt1_start, dt1_end, dt3_start, dt3_end)}") # False

        print("\nTesting time_only_overlap function:")
        t1_start = time(10, 0, 0)
        t1_end   = time(12, 0, 0)
        # Simple overlap
        t2_start = time(11, 0, 0)
        t2_end   = time(13, 0, 0)
        print(f"Time Overlap (10-12 vs 11-13): {check_time_only_overlap(t1_start, t1_end, t2_start, t2_end)}") # True
        # No overlap
        t3_start = time(13, 0, 0)
        t3_end   = time(14, 0, 0)
        print(f"Time No Overlap (10-12 vs 13-14): {check_time_only_overlap(t1_start, t1_end, t3_start, t3_end)}") # False
        # Adjacent
        t4_start = time(12, 0, 0)
        t4_end   = time(13, 0, 0)
        print(f"Time Adjacent (10-12 vs 12-13): {check_time_only_overlap(t1_start, t1_end, t4_start, t4_end)}") # False
        # Contained
        t5_start = time(9, 0, 0)
        t5_end   = time(14, 0, 0)
        print(f"Time Contained (10-12 within 9-14): {check_time_only_overlap(t1_start, t1_end, t5_start, t5_end)}") # True (t1 is contained in t5)
        # Invalid interval
        print(f"Time Invalid Interval (12-10 vs 11-13): {check_time_only_overlap(t1_end, t1_start, t2_start, t2_end)}") # False
        # Non-time input
        print(f"Time Non-Time Input: {check_time_only_overlap(t1_start, t1_end, 'invalid', t2_end)}") # False

        db_conn.close()
    else:
        print("Failed to connect to the database.")
