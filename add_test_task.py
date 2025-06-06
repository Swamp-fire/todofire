#!/usr/bin/env python3
import datetime
import database_manager as db_manager
from task_model import Task
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s - %(message)s')
logger = logging.getLogger(__name__)

def add_scripted_repeating_task():
    logger.info("Attempting to add 'Test Daily Repeating Reminder SCRIPTED' task.")
    conn = None
    try:
        now = datetime.datetime.now()
        # Due time set to 2 minutes from now for testing the first occurrence
        due_datetime = now + datetime.timedelta(minutes=2)
        creation_datetime = now

        task_data = Task(
            id=0,
            title="Test Daily Repeating Reminder SCRIPTED",
            description="This task is for testing daily repeating reminders.",
            duration=10, # 10 minutes work duration
            creation_date=creation_datetime.isoformat(),
            repetition="Daily", # Repeating task
            priority=2, # Medium
            category="Scripted Repeating Test",
            due_date=due_datetime.isoformat(), # First due time
            status="Pending"
            # last_reset_date will be defaulted by Task's __init__
        )

        conn = db_manager.create_connection()
        if not conn:
            logger.error("Failed to connect to the database.")
            return

        db_manager.create_table(conn) # Ensure table exists

        task_id = db_manager.add_task(conn, task_data)

        if task_id:
            logger.info(f"Task '{task_data.title}' added successfully with ID: {task_id}. First Due: {task_data.due_date}, Repetition: {task_data.repetition}")
        else:
            logger.error(f"Failed to add task '{task_data.title}'.")

    except Exception as e:
        logger.error(f"An error occurred in add_scripted_repeating_task: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
            logger.debug("Database connection closed by add_scripted_repeating_task.")

if __name__ == "__main__":
    logger.info("add_test_task.py (for repeating task) script started.")
    add_scripted_repeating_task()
    logger.info("add_test_task.py (for repeating task) script finished.")
