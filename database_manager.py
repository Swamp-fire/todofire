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
    - st1, et1, st2, et2 are datetime.time objects.
    - Handles intervals crossing midnight (e.g., et1 < st1 numerically).
    - Handles "all-day" slots (where stX == etX, implying a task duration >= 24 hours,
      making its time component wrap around to the same time).
    - The end of an interval is considered exclusive.
    - Assumes that zero-duration tasks (where actual task duration_minutes == 0,
      leading to stX == etX but not due to >=24h duration) are filtered out by the
      calling logic in main_app.py before this function is invoked for conflict detection.
    """
    if not (isinstance(st1, datetime.time) and isinstance(et1, datetime.time) and
            isinstance(st2, datetime.time) and isinstance(et2, datetime.time)):
        # Optional: logger.error("Invalid type passed to check_time_only_overlap")
        return False

    # Case 0: One or both intervals represent an "all-day" slot for conflict purposes
    # This happens if task_duration >= 24h, making start_time component == end_time component.
    # An all-day task conflicts with any other task that also has a duration.
    # (Zero-duration tasks are filtered out by caller, so any task here has some duration).
    st1_is_effectively_all_day = (st1 == et1)
    st2_is_effectively_all_day = (st2 == et2)

    if st1_is_effectively_all_day or st2_is_effectively_all_day:
        # If one is all-day, it conflicts with any other timed task (which this function assumes both are).
        # If both are all-day, they also conflict.
        return True

    # Proceed with logic for partial-day intervals, handling midnight crossing
    i1_crosses_midnight = (et1 < st1) # e.g., 23:00 to 01:00
    i2_crosses_midnight = (et2 < st2) # e.g., 22:00 to 00:30

    if not i1_crosses_midnight and not i2_crosses_midnight:
        # Standard overlap for non-crossing intervals: max of starts < min of ends
        # This also implies st1 < et1 and st2 < et2 must hold for this branch.
        return max(st1, st2) < min(et1, et2)
    elif i1_crosses_midnight and not i2_crosses_midnight:
        # Interval 1 (st1,et1) crosses midnight. Interval 2 (st2,et2) does not.
        # Check if Interval 2 overlaps with [st1, time.max] OR [time.min, et1]
        overlap_with_st1_to_midnight = (max(st1, st2) < min(datetime.time.max, et2))
        overlap_with_midnight_to_et1 = (max(datetime.time.min, st2) < min(et1, et2))
        return overlap_with_st1_to_midnight or overlap_with_midnight_to_et1
    elif not i1_crosses_midnight and i2_crosses_midnight:
        # Interval 2 (st2,et2) crosses midnight. Interval 1 (st1,et1) does not.
        # Symmetric to above.
        overlap_with_st2_to_midnight = (max(st2, st1) < min(datetime.time.max, et1))
        overlap_with_midnight_to_et2 = (max(datetime.time.min, st1) < min(et2, et1))
        return overlap_with_st2_to_midnight or overlap_with_midnight_to_et2
    else: # Both intervals cross midnight (e.g., 23:00-01:00 vs 22:00-00:30)
        # If both intervals span across midnight, they are guaranteed to overlap.
        return True

if __name__ == '__main__':
    print("Database Manager Module Direct Test")
    # Test cases for check_time_only_overlap will be added here.
    # Basic DB operations can remain for context if desired, but focus is on time overlap tests.
    db_conn = create_connection() # Keep connection for potential future DB tests
    if not db_conn:
        print("Failed to connect to the database for tests.")
        # Optionally, exit if DB is critical for some setup, but time tests can run without it
        # return

    # Test new check_time_only_overlap function
    print("\n--- Testing NEW check_time_only_overlap (Handles Midnight Crossings & All-Day) ---")
    t = datetime.time # Alias for convenience

    test_cases = [
        # User's scenario
        ("User: (01:00-01:30) vs (01:00-01:30)", t(1,0), t(1,30), t(1,0), t(1,30), True),

        # Standard Non-crossing
        ("T1 (10-12) vs (11-13) Overlap", t(10,0), t(12,0), t(11,0), t(13,0), True),
        ("T2 (10-12) vs (12-13) No Overlap (Adj)", t(10,0), t(12,0), t(12,0), t(13,0), False),
        ("T3 (10-12) vs (13-14) No Overlap", t(10,0), t(12,0), t(13,0), t(14,0), False),
        ("T_Contained (10-14) vs (11-12) Overlap", t(10,0),t(14,0), t(11,0),t(12,0), True),
        ("T_Identical (10-12) vs (10-12) Overlap", t(10,0),t(12,0), t(10,0),t(12,0), True),

        # All-day scenarios
        ("AllDay1: (07-07) vs (08-09)", t(7,0), t(7,0), t(8,0), t(9,0), True),
        ("AllDay2: (08-09) vs (07-07)", t(8,0), t(9,0), t(7,0), t(7,0), True),
        ("AllDay3: (07-07) vs (06-06)", t(7,0), t(7,0), t(6,0), t(6,0), True),
        ("AllDay4: (07-07) vs (06-08) Crosses AllDay Start", t(7,0),t(7,0), t(6,0),t(8,0), True),
        ("AllDay5: (07-07) vs (23-01) AllDay vs Midnight Cross", t(7,0),t(7,0), t(23,0),t(1,0), True),

        # Midnight crossing scenarios
        ("T4 (23-01) vs (00-02) Overlap", t(23,0), t(1,0), t(0,0), t(2,0), True), # I1 crosses, I2 no cross, Overlap
        ("T5 (23-01) vs (22-00) Overlap", t(23,0), t(1,0), t(22,0), t(0,0), True), # I1 crosses, I2 no cross, Overlap
        ("T6 (22-02) vs (23-01) Overlap (Both Cross)", t(22,0), t(2,0), t(23,0), t(1,0), True), # Both Cross
        ("T7 (22-23) vs (23-01) No Overlap (Adj)", t(22,0), t(23,0), t(23,0), t(1,0), False), # I1 no cross, I2 crosses, Adjacent
        ("T8 (02-03) vs (23-01) No Overlap", t(2,0), t(3,0), t(23,0), t(1,0), False), # I1 no cross, I2 crosses, No overlap
        ("T9 (00-02) vs (23-01) Overlap", t(0,0), t(2,0), t(23,0), t(1,0), True), # I1 no cross, I2 crosses, Overlap

        # Additional midnight crossing scenarios
        ("MC1 (22-01) vs (21-23) Overlap", t(22,0), t(1,0), t(21,0), t(23,0), True),
        ("MC2 (22-01) vs (00-02) Overlap", t(22,0), t(1,0), t(0,0), t(2,0), True),
        ("MC3 (22-01) vs (00-23) Overlap (Corrected Desc)", t(22,0), t(1,0), t(0,0), t(23,0), True),
        ("MC4 (08-10) vs (22-01) No Overlap", t(8,0), t(10,0), t(22,0), t(1,0), False),
        ("MC5 (22-01) vs (23-00) Overlap", t(22,0), t(1,0), t(23,0), t(0,0), True),

        # Type errors and other cases
        # T10: Interval 1 (12:00 to 10:00 next day) vs Interval 2 (11:00 to 13:00 same day).
        # They overlap between 12:00 and 13:00 on the first day.
        ("T10 Midnight Cross (12-10) vs Non-Cross (11-13) Overlap", t(12,0), t(10,0), t(11,0), t(13,0), True),
        ("T11 Type Error (10-12) vs ('invalid'-13)", t(10,0), t(12,0), 'invalid', t(13,0), False)
    ]

    all_tests_passed = True
    # Simplified loop assuming test_cases list is now clean without duplicates needing skipping
    for desc, s1, e1, s2, e2, expected in test_cases:
        result = check_time_only_overlap(s1, e1, s2, e2)
        status = "PASSED" if result == expected else "FAILED"
        if result != expected:
            all_tests_passed = False
        print(f"{desc}: Expected={expected}, Got={result} -> {status}")

    if all_tests_passed:
        print("\nAll check_time_only_overlap tests PASSED.")
    else:
        print("\nSome check_time_only_overlap tests FAILED.")

    # Example of how to use check_timeslot_overlap (can be expanded or kept minimal)
    print("\n--- Basic check_timeslot_overlap example ---")
    dt_start1 = datetime.datetime(2024, 1, 1, 10, 0)
    dt_end1 = datetime.datetime(2024, 1, 1, 11, 0)
    dt_start2 = datetime.datetime(2024, 1, 1, 10, 30)
    dt_end2 = datetime.datetime(2024, 1, 1, 11, 30)
    print(f"Full datetime overlap: {check_timeslot_overlap(dt_start1, dt_end1, dt_start2, dt_end2)}")


    if db_conn: # Close if it was opened
        db_conn.close()
        print("\nDB connection closed.")
