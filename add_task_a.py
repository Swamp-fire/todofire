# add_task_a.py
import datetime, database_manager, logging
from task_model import Task
script_logger = logging.getLogger("add_task_a_script")
if not logging.getLogger().hasHandlers(): # Basic config if running standalone
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-8s - %(name)-25s - %(message)s')

def add_task_a():
    conn = database_manager.create_connection()
    if not conn:
        script_logger.error("ADD_TASK_A: Failed to connect to DB.")
        return
    database_manager.create_table(conn)
    now = datetime.datetime.now()
    # Task A: Daily, 01:00 AM, 30 min duration (due in a couple of days)
    task_a_due_datetime = (now + datetime.timedelta(days=2)).replace(hour=1, minute=0, second=0, microsecond=0)
    task_a_creation_time = now - datetime.timedelta(seconds=20) # Ensure creation is before first possible log processing
    task_a_data = {
        'id':None,'title':"Daily Task A 1AM",'description':"Base daily task for conflict test.",'duration':30,
        'creation_date':task_a_creation_time.isoformat(),'repetition':'Daily','priority':1,'category':"ConflictTest",
        'due_date':task_a_due_datetime.isoformat(),'status':'Pending','last_reset_date':task_a_creation_time.date().isoformat()
    }
    task_a_obj = Task(**task_a_data)
    task_a_id = database_manager.add_task(conn, task_a_obj)
    if task_a_id:
        script_logger.info(f"ADD_TASK_A: Script added Task A '{task_a_obj.title}' (ID {task_a_id}), Due: {task_a_obj.due_date}")
    else:
        script_logger.error(f"ADD_TASK_A: Script failed to add Task A '{task_a_obj.title}'.")
    conn.close()
if __name__ == '__main__': add_task_a()
