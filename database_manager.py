import sqlite3
from sqlite3 import Error
from task_model import Task # Assuming task_model.py is in the same directory

def create_connection(db_file_name: str = "tasks.db") -> sqlite3.Connection | None:
    """Create a database connection to an SQLite database specified by db_file_name"""
    conn = None
    try:
        conn = sqlite3.connect(db_file_name)
        print(f"SQLite version: {sqlite3.sqlite_version}")
        print(f"Successfully connected to {db_file_name}")
        return conn
    except Error as e:
        print(f"Error connecting to database: {e}")
        return None

def create_table(conn: sqlite3.Connection) -> None:
    """Create a table from the create_table_sql statement
    :param conn: Connection object
    """
    create_table_sql = """CREATE TABLE IF NOT EXISTS Tasks (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT NOT NULL,
                            description TEXT,
                            duration INTEGER,
                            creation_date TEXT NOT NULL,
                            repetition TEXT,
                            priority INTEGER,
                            category TEXT
                        );"""
    try:
        cursor = conn.cursor()
        cursor.execute(create_table_sql)
        print("Tasks table created successfully (if it didn't exist).")
    except Error as e:
        print(f"Error creating table: {e}")

def add_task(conn: sqlite3.Connection, task: Task) -> int | None:
    """
    Add a new task into the Tasks table
    :param conn: Connection object
    :param task: Task object
    :return: task id
    """
    sql = '''INSERT INTO Tasks(title, description, duration, creation_date, repetition, priority, category)
             VALUES(?,?,?,?,?,?,?)'''
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (task.title, task.description, task.duration, task.creation_date,
                           task.repetition, task.priority, task.category))
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        print(f"Error adding task: {e}")
        return None

def get_task(conn: sqlite3.Connection, task_id: int) -> Task | None:
    """
    Query tasks by id
    :param conn: the Connection object
    :param task_id:
    :return: Task object or None
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Tasks WHERE id=?", (task_id,))
        row = cursor.fetchone()
        if row:
            return Task(id=row[0], title=row[1], description=row[2], duration=row[3],
                        creation_date=row[4], repetition=row[5], priority=row[6], category=row[7])
        else:
            return None
    except Error as e:
        print(f"Error getting task: {e}")
        return None

def get_all_tasks(conn: sqlite3.Connection) -> list[Task]:
    """
    Query all rows in the Tasks table
    :param conn: the Connection object
    :return: A list of Task objects
    """
    tasks_list = []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Tasks")
        rows = cursor.fetchall()
        for row in rows:
            tasks_list.append(Task(id=row[0], title=row[1], description=row[2], duration=row[3],
                                   creation_date=row[4], repetition=row[5], priority=row[6], category=row[7]))
        return tasks_list
    except Error as e:
        print(f"Error getting all tasks: {e}")
        return []

def update_task(conn: sqlite3.Connection, task: Task) -> bool:
    """
    update title, description, duration, creation_date, repetition, priority, and category of a task
    :param conn:
    :param task:
    :return: True if updated, False otherwise
    """
    sql = '''UPDATE Tasks
             SET title = ?,
                 description = ?,
                 duration = ?,
                 creation_date = ?,
                 repetition = ?,
                 priority = ?,
                 category = ?
             WHERE id = ?'''
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (task.title, task.description, task.duration, task.creation_date,
                           task.repetition, task.priority, task.category, task.id))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        print(f"Error updating task: {e}")
        return False

def delete_task(conn: sqlite3.Connection, task_id: int) -> bool:
    """
    Delete a task by task id
    :param conn: Connection to the SQLite database
    :param task_id: id of the task
    :return: True if deleted, False otherwise
    """
    sql = 'DELETE FROM Tasks WHERE id=?'
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (task_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        print(f"Error deleting task: {e}")
        return False

if __name__ == '__main__':
    db_name = "tasks_main.db"
    # Create a database connection
    connection = create_connection(db_name)

    if connection is not None:
        # Create tasks table
        create_table(connection)

        # Example Usage (optional, can be removed or commented out)
        # from datetime import datetime

        # Create a dummy task
        # current_time_iso = datetime.now().isoformat()
        # task1 = Task(id=0, title="Grocery Shopping", description="Buy milk, eggs, bread",
        #              duration=60, creation_date=current_time_iso, repetition="Weekly",
        #              priority=1, category="Home")

        # Add the task
        # task1_id = add_task(connection, task1)
        # if task1_id:
        #     print(f"Task added with ID: {task1_id}")

        #     # Retrieve the task
        #     retrieved_task = get_task(connection, task1_id)
        #     if retrieved_task:
        #         print(f"Retrieved Task: {retrieved_task.title}, Due: {retrieved_task.creation_date}")

        #     # Update the task
        #     # retrieved_task.description = "Buy milk, eggs, bread, and cheese"
        #     # if update_task(connection, retrieved_task):
        #     #     print(f"Task {retrieved_task.id} updated successfully.")
        #     #     updated_retrieved_task = get_task(connection, task1_id)
        #     #     if updated_retrieved_task:
        #     #            print(f"Updated Task Description: {updated_retrieved_task.description}")


        #     # Get all tasks
        #     # all_tasks = get_all_tasks(connection)
        #     # print(f"All tasks ({len(all_tasks)}):")
        #     # for t in all_tasks:
        #     #     print(f"  - {t.title} (ID: {t.id})")

        #     # Delete the task
        #     # if delete_task(connection, task1_id):
        #     #     print(f"Task {task1_id} deleted successfully.")
        #     # else:
        #     #     print(f"Failed to delete task {task1_id}.")

        # Close the connection
        connection.close()
        print(f"Connection to {db_name} closed.")
    else:
        print(f"Error! Cannot create the database connection to {db_name}.")
