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

def check_time_only_overlap(st1: datetime.time, et1: datetime.time,
                               st2: datetime.time, et2: datetime.time) -> bool:
    """
    Checks if two time-of-day intervals [st1, et1) and [st2, et2) overlap.
    Handles intervals that cross midnight (e.g., where et1 < st1 numerically).
    The end of the interval is considered exclusive.
    Assumes durations are positive and less than 24 hours for simplicity of this check.
    """
    if not (isinstance(st1, datetime.time) and isinstance(et1, datetime.time) and
            isinstance(st2, datetime.time) and isinstance(et2, datetime.time)):
        print(f"Warning (check_time_only_overlap): Non-datetime.time type passed: {type(st1)}, {type(et1)}, {type(st2)}, {type(et2)}")
        return False

    # Normalize times to represent intervals on a potential two-day span if they cross midnight
    i1_crosses_midnight = (et1 < st1)
    i2_crosses_midnight = (et2 < st2)

    # Case 1: Both intervals DO NOT cross midnight (simple case)
    if not i1_crosses_midnight and not i2_crosses_midnight:
        if st1 >= et1 or st2 >= et2: # Invalid interval if not crossing midnight
             print(f"Warning (check_time_only_overlap): Invalid non-crossing time interval: {st1}-{et1} or {st2}-{et2}")
             return False
        return max(st1, st2) < min(et1, et2)

    # Case 2: Interval 1 crosses midnight, Interval 2 does NOT
    elif i1_crosses_midnight and not i2_crosses_midnight:
        if st2 >= et2: # Invalid interval for non-crossing
            print(f"Warning (check_time_only_overlap): Invalid non-crossing time interval 2: {st2}-{et2}")
            return False
        # Check if Interval 2 overlaps with [i1_st, time.max] OR [time.min, i1_et]
        overlap_part1 = (max(st1, st2) < min(datetime.time.max, et2))
        overlap_part2 = (max(datetime.time.min, st2) < min(et1, et2))
        return overlap_part1 or overlap_part2

    # Case 3: Interval 2 crosses midnight, Interval 1 does NOT
    elif not i1_crosses_midnight and i2_crosses_midnight:
        if st1 >= et1: # Invalid interval for non-crossing
            print(f"Warning (check_time_only_overlap): Invalid non-crossing time interval 1: {st1}-{et1}")
            return False
        # Symmetric to Case 2
        overlap_part1 = (max(st2, st1) < min(datetime.time.max, et1))
        overlap_part2 = (max(datetime.time.min, st1) < min(et2, et1))
        return overlap_part1 or overlap_part2

    # Case 4: Both intervals cross midnight
    else: # i1_crosses_midnight and i2_crosses_midnight
        # If both intervals span across midnight, they are guaranteed to overlap
        return True


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
            # ... (existing task tests remain here) ...
            print(f"Added task with ID: {task_id}")
            # ...

        # Test check_timeslot_overlap function (existing tests)
        print("\n--- Testing check_timeslot_overlap ---")
        dt1_start = datetime.datetime(2024, 1, 1, 10, 0, 0)
        dt1_end   = datetime.datetime(2024, 1, 1, 11, 0, 0)
        dt2_start = datetime.datetime(2024, 1, 1, 10, 30, 0)
        dt2_end   = datetime.datetime(2024, 1, 1, 11, 30, 0)
        dt3_start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        dt3_end   = datetime.datetime(2024, 1, 1, 13, 0, 0)
        dt4_start = datetime.datetime(2024, 1, 1, 9, 0, 0)
        dt4_end   = datetime.datetime(2024, 1, 1, 12, 0, 0)
        dt5_start = datetime.datetime(2024, 1, 1, 10, 0, 0)
        dt5_end   = datetime.datetime(2024, 1, 1, 11, 0, 0)
        dt6_start = datetime.datetime(2024, 1, 1, 11, 0, 0)
        dt6_end   = datetime.datetime(2024, 1, 1, 12, 0, 0)
        print(f"Interval 1: {dt1_start} - {dt1_end}")
        print(f"Interval 2 (overlaps): {dt2_start} - {dt2_end} -> Overlap? {check_timeslot_overlap(dt1_start, dt1_end, dt2_start, dt2_end)}")
        print(f"Interval 3 (no overlap): {dt3_start} - {dt3_end} -> Overlap? {check_timeslot_overlap(dt1_start, dt1_end, dt3_start, dt3_end)}")
        print(f"Interval 4 (contains 1): {dt4_start} - {dt4_end} -> Overlap? {check_timeslot_overlap(dt1_start, dt1_end, dt4_start, dt4_end)}")
        print(f"Interval 5 (same as 1): {dt5_start} - {dt5_end} -> Overlap? {check_timeslot_overlap(dt1_start, dt1_end, dt5_start, dt5_end)}")
        print(f"Interval 6 (adjacent to 1): {dt6_start} - {dt6_end} -> Overlap? {check_timeslot_overlap(dt1_start, dt1_end, dt6_start, dt6_end)}")
        print(f"Invalid interval (end before start): Overlap? {check_timeslot_overlap(dt1_end, dt1_start, dt2_start, dt2_end)}")
        print(f"Non-datetime input: Overlap? {check_timeslot_overlap(dt1_start, dt1_end, 'not-a-datetime', dt2_end)}")

        # Test new check_time_only_overlap function
        print("\n--- Testing check_time_only_overlap (Handles Midnight Crossings) ---")
        t = datetime.time # Alias for convenience
        # Non-crossing cases
        print(f"T1 (10-12) vs (11-13) Overlap: {check_time_only_overlap(t(10), t(12), t(11), t(13))}") # Expected: True
        print(f"T2 (10-12) vs (12-13) No Overlap (Adj): {check_time_only_overlap(t(10), t(12), t(12), t(13))}") # Expected: False
        print(f"T3 (10-12) vs (13-14) No Overlap: {check_time_only_overlap(t(10), t(12), t(13), t(14))}") # Expected: False
        print(f"T_Contained (10-14) vs (11-12) Overlap: {check_time_only_overlap(t(10),t(14), t(11),t(12))}") # Expected: True
        print(f"T_Identical (10-12) vs (10-12) Overlap: {check_time_only_overlap(t(10),t(12), t(10),t(12))}") # Expected: True

        # Crossing midnight cases
        # ct1: 23:00 to 01:00 (next day) | ct2: 00:00 to 02:00 (overlaps second part of ct1)
        print(f"T4 (23-01) vs (00-02) Overlap: {check_time_only_overlap(t(23,0), t(1,0), t(0,0), t(2,0))}") # Expected: True
        # ct1: 23:00 to 01:00 | ct2: 22:00 to 00:00 (overlaps first part of ct1)
        print(f"T5 (23-01) vs (22-00) Overlap: {check_time_only_overlap(t(23,0), t(1,0), t(22,0), t(0,0))}") # Expected: True
        # ct1: 22:00 to 02:00 | ct2: 23:00 to 01:00 (ct2 contained in ct1, both cross)
        print(f"T6 (22-02) vs (23-01) Overlap (Both Cross): {check_time_only_overlap(t(22,0), t(2,0), t(23,0), t(1,0))}") # Expected: True
        # ct1: 22:00 to 23:00 (No cross) | ct2: 23:00 to 01:00 (Cross) -> No Overlap (adjacent)
        print(f"T7 (22-23) vs (23-01) No Overlap (Adj): {check_time_only_overlap(t(22,0), t(23,0), t(23,0), t(1,0))}") # Expected: False
        # ct1: 02:00 to 03:00 (No cross) | ct2: 23:00 to 01:00 (Cross) -> No Overlap
        print(f"T8 (02-03) vs (23-01) No Overlap: {check_time_only_overlap(t(2,0), t(3,0), t(23,0), t(1,0))}") # Expected: False
        # ct1: 00:00 to 02:00 (No cross) | ct2: 23:00 to 01:00 (Cross, overlaps with ct1's end)
        print(f"T9 (00-02) vs (23-01) Overlap: {check_time_only_overlap(t(0,0), t(2,0), t(23,0), t(1,0))}") # Expected: True

        # Invalid intervals (start_time >= end_time for non-crossing)
        print(f"T10 (12-10) vs (11-13) Invalid: {check_time_only_overlap(t(12,0), t(10,0), t(11,0), t(13,0))}") # Expected: False
        # Type errors
        print(f"T11 (10-12) vs ('invalid'-13) Type Error: {check_time_only_overlap(t(10,0), t(12,0), 'invalid', t(13,0))}") # Expected: False

        db_conn.close()
    else:
        print("Failed to connect to the database.")
