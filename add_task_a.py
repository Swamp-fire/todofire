# add_task_a.py
import datetime
import database_manager
from task_model import Task
import logging

script_logger = logging.getLogger("add_task_a_script")
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-8s - %(name)-25s - %(message)s')

def add_task_a_for_stability_test():
    conn = database_manager.create_connection()
    if not conn:
        script_logger.error("ADD_TASK_A: Failed to connect to DB.")
        return

    database_manager.create_table(conn)

    now = datetime.datetime.now()
    task_a_due_datetime = (now + datetime.timedelta(days=2)).replace(hour=1, minute=0, second=0, microsecond=0)
    task_a_creation_time = now - datetime.timedelta(seconds=20)

    task_a_data = {
        'id': None, # Will be set by DB
        'title': "Daily Task A 1AM (Stability Test)",
        'description': "Task A for stability check after conflict logic fixes.",
        'duration': 30, # minutes
        'creation_date': task_a_creation_time.isoformat(),
        'repetition': 'Daily',
        'priority': 1,
        'category': "StabilityCheck",
        'due_date': task_a_due_datetime.isoformat(),
        'status': 'Pending',
        'last_reset_date': task_a_creation_time.date().isoformat()
    }
    task_a_obj = Task(**task_a_data)
    task_a_id = database_manager.add_task(conn, task_a_obj)

    if task_a_id:
        script_logger.info(f"ADD_TASK_A: Successfully added Task A '{task_a_obj.title}' with ID {task_a_id}, Due: {task_a_obj.due_date}")
    else:
        script_logger.error(f"ADD_TASK_A: Failed to add Task A '{task_a_obj.title}'.")

    conn.close()

if __name__ == '__main__':
    add_task_a_for_stability_test()
