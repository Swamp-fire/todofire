import datetime
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import database_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_repeating_tasks():
    logger.info("Scheduler job 'check_repeating_tasks' started.")
    conn = None
    try:
        conn = database_manager.create_connection()
        if not conn:
            logger.error("Failed to connect to the database for checking repeating tasks.")
            return

        tasks = database_manager.get_all_tasks(conn)
        if not tasks:
            logger.info("No tasks found in the database for repetition check.")
            return

        today = datetime.date.today()
        tasks_reset_count = 0

        for task in tasks:
            if not task.repetition or task.repetition.lower() == 'none':
                continue

            if not task.last_reset_date:
                logger.warning(f"Task '{task.title}' (ID: {task.id}) has no last_reset_date. Skipping.")
                continue

            try:
                last_reset_dt = datetime.date.fromisoformat(task.last_reset_date)
            except ValueError:
                logger.error(f"Invalid last_reset_date format for Task '{task.title}' (ID: {task.id}): {task.last_reset_date}. Skipping.")
                continue

            needs_reset = False
            if task.repetition == 'Daily':
                if today > last_reset_dt: needs_reset = True
            elif task.repetition == 'Weekly':
                if today >= last_reset_dt + datetime.timedelta(days=7): needs_reset = True
            elif task.repetition == 'Monthly':
                if today > last_reset_dt:
                    if today.month != last_reset_dt.month or today.year != last_reset_dt.year:
                        if today.day >= last_reset_dt.day:
                            needs_reset = True
            elif task.repetition == 'Yearly':
                if today > last_reset_dt:
                    if today.year > last_reset_dt.year:
                        if (today.month > last_reset_dt.month) or \
                           (today.month == last_reset_dt.month and today.day >= last_reset_dt.day):
                            needs_reset = True

            if needs_reset:
                original_status = task.status
                task.status = "Pending"
                task.last_reset_date = today.isoformat()
                if database_manager.update_task(conn, task):
                    logger.info(f"Task '{task.title}' (ID: {task.id}) reset for {task.repetition} repetition (status from '{original_status}' to 'Pending').")
                    tasks_reset_count += 1
                else:
                    logger.error(f"Failed to update Task '{task.title}' (ID: {task.id}) after reset.")

        if tasks_reset_count == 0:
            logger.info("Scheduler job 'check_repeating_tasks' completed. No tasks required resetting.")
        else:
            logger.info(f"Scheduler job 'check_repeating_tasks' completed. {tasks_reset_count} tasks were reset.")

    except Exception as e:
        logger.error(f"General error during 'check_repeating_tasks': {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
            logger.debug("DB connection closed after check_repeating_tasks.")


def schedule_task_reminders(scheduler, reminder_queue): # MODIFIED: Added reminder_queue
    """
    Scans tasks from the database and schedules or updates reminders.
    Removes reminders for tasks that are completed, deleted, or no longer have a due date.
    """
    logger.info("Scheduler job 'schedule_task_reminders' started.")
    conn = None
    active_reminder_job_ids = set()
    scheduled_count = 0
    updated_count = 0

    try:
        conn = database_manager.create_connection()
        if not conn:
            logger.error("Failed to connect to the database for scheduling reminders.")
            return

        tasks = database_manager.get_all_tasks(conn)
        if not tasks:
            logger.info("No tasks found in the database to schedule reminders for.")

        now = datetime.datetime.now()

        for task in tasks:
            job_id = f"reminder_{task.id}"

            if not task.due_date or task.status == 'Completed':
                continue

            try:
                due_datetime = datetime.datetime.fromisoformat(task.due_date)
            except ValueError:
                logger.error(f"Invalid due_date format for Task '{task.title}' (ID: {task.id}): {task.due_date}. Skipping reminder.")
                continue

            active_reminder_job_ids.add(job_id)

            trigger_details = None
            is_new_job = scheduler.get_job(job_id) is None

            if not task.repetition or task.repetition.lower() == 'none':
                if due_datetime < now:
                    logger.info(f"One-time reminder for Task '{task.title}' (ID: {task.id}) is in the past. Skipping.")
                    active_reminder_job_ids.remove(job_id)
                    continue
                trigger_details = {'trigger': 'date', 'run_date': due_datetime}
            else:
                cron_params = {'hour': due_datetime.hour, 'minute': due_datetime.minute, 'start_date': now}

                if task.repetition == 'Daily':
                    trigger_details = {'trigger': 'cron', **cron_params}
                elif task.repetition == 'Weekly':
                    trigger_details = {'trigger': 'cron', 'day_of_week': due_datetime.weekday(), **cron_params}
                elif task.repetition == 'Monthly':
                    trigger_details = {'trigger': 'cron', 'day': due_datetime.day, **cron_params}
                elif task.repetition == 'Yearly':
                    trigger_details = {'trigger': 'cron', 'month': due_datetime.month, 'day': due_datetime.day, **cron_params}
                else:
                    logger.warning(f"Unknown repetition '{task.repetition}' for Task '{task.title}' (ID: {task.id}). Skipping reminder.")
                    active_reminder_job_ids.remove(job_id)
                    continue

            if trigger_details:
                try:
                    scheduler.add_job(
                        trigger_reminder_action,
                        args=[task.id, task.title, reminder_queue], # MODIFIED: Added reminder_queue
                        id=job_id,
                        replace_existing=True,
                        **trigger_details
                    )
                    if is_new_job:
                        scheduled_count +=1
                        logger.info(f"Scheduled reminder for Task '{task.title}' (ID: {task.id}) with trigger: {trigger_details}")
                    else:
                        updated_count +=1
                        logger.info(f"Updated reminder for Task '{task.title}' (ID: {task.id}) with trigger: {trigger_details}")
                except Exception as e_job:
                    logger.error(f"Failed to add/update job for Task '{task.title}' (ID: {task.id}): {e_job}", exc_info=True)
                    if job_id in active_reminder_job_ids: active_reminder_job_ids.remove(job_id)

        removed_count = 0
        if scheduler.running:
            existing_jobs = scheduler.get_jobs()
            for job in existing_jobs:
                if job.id.startswith("reminder_") and job.id not in active_reminder_job_ids:
                    try:
                        scheduler.remove_job(job.id)
                        removed_count += 1
                        logger.info(f"Removed stale reminder job: {job.id}")
                    except Exception as e_remove:
                         logger.error(f"Failed to remove stale job {job.id}: {e_remove}", exc_info=True)

        summary_log = (f"Scheduler job 'schedule_task_reminders' completed. "
                       f"New: {scheduled_count}, Updated: {updated_count}, Removed Stale: {removed_count}.")
        if scheduled_count == 0 and updated_count == 0 and removed_count == 0 and tasks:
             summary_log += " No changes to reminder schedules were needed."
        elif not tasks and removed_count == 0 :
             summary_log = "Scheduler job 'schedule_task_reminders' completed. No tasks found and no stale jobs to remove."
        logger.info(summary_log)

    except Exception as e:
        logger.error(f"General error during 'schedule_task_reminders': {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
            logger.debug("DB connection closed after schedule_task_reminders.")


def initialize_scheduler(reminder_queue): # MODIFIED: Added reminder_queue
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(check_repeating_tasks, 'interval', hours=1, id='job_check_repetition')

    try:
        scheduler.add_job(schedule_task_reminders, 'interval', minutes=15,
                          args=[scheduler, reminder_queue], id='job_rescheduler_reminders') # MODIFIED: Added reminder_queue

        scheduler.start()
        logger.info("BackgroundScheduler initialized and started.")

        schedule_task_reminders(scheduler, reminder_queue) # MODIFIED: Added reminder_queue

        logger.info("Job 'check_repeating_tasks' scheduled every 1 hour. Job 'schedule_task_reminders' scheduled every 15 minutes.")

    except Exception as e:
        logger.error(f"Failed to start or fully configure scheduler: {e}", exc_info=True)
        if scheduler.running:
            scheduler.shutdown()
        return None
    return scheduler

def trigger_reminder_action(task_id: int, task_title: str, reminder_queue): # MODIFIED: Added reminder_queue
    """
    Action for when a task reminder is triggered by the scheduler.
    This function queues the reminder information for the main UI thread to process.
    """
    logger.info(f"Queuing reminder for Task ID: {task_id} - Title: '{task_title}'")
    try:
        reminder_queue.put({'task_id': task_id, 'task_title': task_title})
    except Exception as e:
        logger.error(f"Failed to queue reminder for Task ID {task_id}: {e}", exc_info=True)

if __name__ == '__main__':
    # This block is for direct testing of the scheduler logic.
    logger.info("Testing scheduler_manager.py directly...")

    # ... (rest of the __main__ block from previous version, potentially adapted for new signatures if run directly)
    # For this subtask, the __main__ block's direct execution isn't the focus,
    # but ensuring it doesn't break due to signature changes is good.
    # However, direct execution would now require a dummy queue.

    # Example of how one might test with a dummy queue if running this file directly:
    # import queue
    # test_q = queue.Queue()
    # class MockScheduler:
    #     def get_job(self, job_id): return None
    #     def add_job(self, *args, **kwargs): print(f"MockScheduler: add_job called with {args}, {kwargs}")
    #     def remove_job(self, job_id): print(f"MockScheduler: remove_job called for {job_id}")
    #     def get_jobs(self): return []
    #     def running(self): return True # Simulate running for get_jobs() call
    # mock_scheduler_instance = MockScheduler()
    # schedule_task_reminders(mock_scheduler_instance, test_q)
    # initialize_scheduler(test_q) # This would start the actual scheduler if not mocked.

    logger.info("Scheduler_manager.py direct test section finished (main execution part simplified for this pass).")
