import datetime
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import database_manager

# Note: main_app.py should ideally be the one calling basicConfig.
# If this module is run standalone for testing, its __main__ block handles it.
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
        logger.info(f"Fetched {len(tasks)} tasks for repetition check.")
        if not tasks:
            return

        today = datetime.date.today()
        tasks_reset_count = 0

        for task in tasks:
            logger.debug(f"Checking repetition for Task ID: {task.id}, Title: '{task.title}', Rep: {task.repetition}, LastReset: {task.last_reset_date}, Status: {task.status}")
            if not task.repetition or task.repetition.lower() == 'none':
                continue

            if not task.last_reset_date:
                logger.warning(f"Task '{task.title}' (ID: {task.id}) has no last_reset_date for repetition check. Skipping.")
                continue

            try:
                last_reset_dt = datetime.date.fromisoformat(task.last_reset_date)
            except ValueError:
                logger.error(f"Invalid last_reset_date format for Task '{task.title}' (ID: {task.id}): {task.last_reset_date}. Skipping repetition check.", exc_info=True)
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
                logger.debug(f"Attempting to reset task ID {task.id}. New status: Pending, New Last Reset: {task.last_reset_date}")
                if database_manager.update_task(conn, task):
                    logger.info(f"Task '{task.title}' (ID: {task.id}) reset for {task.repetition} repetition (status from '{original_status}' to 'Pending').")
                    tasks_reset_count += 1
                else:
                    logger.error(f"Failed to update Task '{task.title}' (ID: {task.id}) after reset attempt.")

        if tasks_reset_count == 0 and len(tasks) > 0 :
            logger.info("Scheduler job 'check_repeating_tasks' completed. No tasks required resetting.")
        elif tasks_reset_count > 0:
            logger.info(f"Scheduler job 'check_repeating_tasks' completed. {tasks_reset_count} tasks were reset.")

    except Exception as e:
        logger.error(f"General error during 'check_repeating_tasks': {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
            logger.debug("DB connection closed after check_repeating_tasks.")


def schedule_task_reminders(scheduler, reminder_queue):
    logger.info("Scheduler job 'schedule_task_reminders' started.")
    conn = None
    active_reminder_job_ids = set()
    scheduled_count = 0
    updated_count = 0
    skipped_past_one_time = 0
    skipped_no_trigger = 0

    try:
        conn = database_manager.create_connection()
        if not conn:
            logger.error("Failed to connect to the database for scheduling reminders.")
            return

        tasks = database_manager.get_all_tasks(conn)
        logger.info(f"Fetched {len(tasks)} tasks from DB for reminder scheduling.")
        if not tasks and not any(job.id.startswith("reminder_") for job in scheduler.get_jobs()):
            logger.info("No tasks found and no existing reminder jobs to clean. Exiting 'schedule_task_reminders'.")
            if conn: conn.close()
            return

        now = datetime.datetime.now()

        for task in tasks:
            logger.debug(f"Processing task for reminder: ID={task.id}, Title='{task.title}', Due='{task.due_date}', Rep='{task.repetition}', Status='{task.status}'")
            job_id = f"reminder_{task.id}"

            if not task.due_date or task.status == 'Completed':
                logger.debug(f"Skipping reminder for task ID {task.id}: No due date or task is completed.")
                continue

            try:
                due_datetime = datetime.datetime.fromisoformat(task.due_date)
            except ValueError:
                logger.error(f"Invalid due_date format for Task '{task.title}' (ID: {task.id}): {task.due_date}. Skipping reminder.", exc_info=True)
                continue

            active_reminder_job_ids.add(job_id)
            trigger_details = None
            current_job = scheduler.get_job(job_id)
            is_new_job = current_job is None

            if not task.repetition or task.repetition.lower() == 'none':
                if due_datetime < now:
                    logger.info(f"One-time reminder for Task '{task.title}' (ID: {task.id}, Due: {due_datetime.isoformat()}) is in the past. Skipping.")
                    if job_id in active_reminder_job_ids: active_reminder_job_ids.remove(job_id)
                    skipped_past_one_time +=1
                    if current_job:
                         logger.debug(f"Removing past one-time job: {job_id}")
                         try: scheduler.remove_job(job_id)
                         except Exception as e_rem: logger.error(f"Error removing past job {job_id}: {e_rem}", exc_info=True)
                    continue
                trigger_details = {'trigger': 'date', 'run_date': due_datetime}
            else:
                cron_params = {'hour': due_datetime.hour, 'minute': due_datetime.minute,
                               'start_date': datetime.datetime.combine(datetime.date.today(), datetime.time.min) }
                if due_datetime < now and task.repetition == 'Daily':
                     cron_params['start_date'] = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time.min)

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
                    if job_id in active_reminder_job_ids: active_reminder_job_ids.remove(job_id)
                    skipped_no_trigger +=1
                    continue

            if trigger_details:
                job_args = [task.id, task.title, reminder_queue]
                logger.debug(f"Attempting to add/update job: ID='{job_id}', Trigger='{trigger_details.get('trigger')}', Params={trigger_details}, Args={job_args[:2]}..Q)")
                try:
                    scheduler.add_job(
                        trigger_reminder_action,
                        args=job_args,
                        id=job_id,
                        replace_existing=True,
                        misfire_grace_time=300,
                        **trigger_details
                    )
                    if is_new_job:
                        scheduled_count +=1
                        logger.info(f"Scheduled reminder for Task '{task.title}' (ID: {task.id}). Trigger: {trigger_details}")
                    else:
                        updated_count +=1
                        logger.info(f"Updated reminder for Task '{task.title}' (ID: {task.id}). Trigger: {trigger_details}")
                except Exception as e_job:
                    logger.error(f"Failed to add/update job for Task '{task.title}' (ID: {task.id}): {e_job}", exc_info=True)
                    if job_id in active_reminder_job_ids: active_reminder_job_ids.remove(job_id)
            else:
                skipped_no_trigger +=1

        removed_count = 0
        if scheduler.running:
            existing_jobs = scheduler.get_jobs()
            logger.debug(f"Currently {len(existing_jobs)} jobs in scheduler. Checking for stale reminder jobs...")
            for job in existing_jobs:
                if job.id.startswith("reminder_") and job.id not in active_reminder_job_ids:
                    logger.info(f"Removing stale reminder job: {job.id} (next run: {job.next_run_time if job.next_run_time else 'N/A'})")
                    try:
                        scheduler.remove_job(job.id)
                        removed_count += 1
                    except Exception as e_remove:
                         logger.error(f"Failed to remove stale job {job.id}: {e_remove}", exc_info=True)

        summary_log = (f"Scheduler job 'schedule_task_reminders' completed. "
                       f"Tasks processed: {len(tasks)}. "
                       f"New reminders: {scheduled_count}, Updated: {updated_count}, "
                       f"Skipped (past one-time): {skipped_past_one_time}, Skipped (no trigger): {skipped_no_trigger}, "
                       f"Removed stale: {removed_count}.")
        logger.info(summary_log)

        if logger.isEnabledFor(logging.DEBUG):
            current_jobs_summary = ["Current scheduler jobs:"]
            for job in scheduler.get_jobs():
                current_jobs_summary.append(f"  - ID: {job.id}, Next Run: {job.next_run_time}, Trigger: {job.trigger}")
            logger.debug("\n".join(current_jobs_summary))

    except Exception as e:
        logger.error(f"General error during 'schedule_task_reminders': {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
            logger.debug("DB connection closed after schedule_task_reminders.")

def initialize_scheduler(reminder_queue):
    scheduler = BackgroundScheduler(daemon=True)
    job_repetition_id = 'job_check_repetition'
    job_rescheduler_id = 'job_rescheduler_reminders'
    interval_reschedule_minutes = 5 # RESTORED Original value (was 15, then 5, then 20s for test)

    scheduler.add_job(check_repeating_tasks, 'interval', hours=1, id=job_repetition_id)
    logger.info(f"Added interval job for 'check_repeating_tasks': ID='{job_repetition_id}', Hours=1")

    try:
        scheduler.add_job(schedule_task_reminders, 'interval', minutes=interval_reschedule_minutes,
                          args=[scheduler, reminder_queue], id=job_rescheduler_id)
        logger.info(f"Added interval job for 'schedule_task_reminders': ID='{job_rescheduler_id}', Minutes={interval_reschedule_minutes}")

        scheduler.start()
        logger.info("BackgroundScheduler initialized and started.")

        logger.info("Performing initial scan and scheduling of reminders...")
        schedule_task_reminders(scheduler, reminder_queue)

    except Exception as e:
        logger.error(f"Failed to start or fully configure scheduler: {e}", exc_info=True)
        if scheduler.running:
            scheduler.shutdown()
        return None
    return scheduler

def trigger_reminder_action(task_id: int, task_title: str, reminder_queue):
    logger.debug(f"trigger_reminder_action called for Task ID: {task_id}, Title: '{task_title}'")
    data_to_queue = {'task_id': task_id, 'task_title': task_title}
    logger.debug(f"Preparing to put data on reminder_queue: {data_to_queue}")
    try:
        reminder_queue.put(data_to_queue)
        logger.info(f"Successfully queued reminder for Task ID: {task_id}")
    except Exception as e:
        logger.error(f"Failed to queue reminder for Task ID {task_id}: {e}", exc_info=True)

if __name__ == '__main__':
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logger.info("Testing scheduler_manager.py directly...")

    import queue
    test_q = queue.Queue()

    class MockTask:
        def __init__(self, id, title, repetition, last_reset_date, status="Pending", due_date=None, description="", duration=0, creation_date=None, priority=1, category=""):
            self.id = id; self.title = title; self.repetition = repetition; self.last_reset_date = last_reset_date
            self.status = status; self.due_date = due_date; self.description = description; self.duration = duration
            self.creation_date = creation_date if creation_date else datetime.datetime.now().isoformat(); self.priority = priority; self.category = category

    mock_tasks_db_for_test = [
        MockTask(1, "Daily Past Reminder", "Daily", "2023-01-01", "Pending", (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()),
        MockTask(2, "One-Time Future Reminder", "None", "2023-01-01", "Pending", (datetime.datetime.now() + datetime.timedelta(minutes=1)).isoformat()),
        MockTask(3, "Completed Task", "Daily", "2023-01-01", "Completed", (datetime.datetime.now() + datetime.timedelta(days=1)).isoformat()),
        MockTask(4, "No Due Date", "Daily", "2023-01-01", "Pending", None),
        MockTask(5, "Daily Future Reminder", "Daily", "2023-01-01", "Pending", (datetime.datetime.now() + datetime.timedelta(days=1, hours=2)).isoformat()),
    ]

    original_get_all_tasks = database_manager.get_all_tasks
    database_manager.get_all_tasks = lambda conn: mock_tasks_db_for_test

    class MockScheduler:
        def __init__(self): self.jobs = {}
        def get_job(self, job_id): return self.jobs.get(job_id)
        def add_job(self, func, args, id, replace_existing, **trigger_details):
            logger.info(f"(MockScheduler) add_job: id={id}, args={args[:2]}..., trigger={trigger_details}")
            class MockJob:
                def __init__(self, id, trigger, next_run_time=None):
                    self.id = id; self.trigger = trigger
                    if trigger_details.get('trigger') == 'date':
                         self.next_run_time = trigger_details.get('run_date')
                    else:
                         self.next_run_time = datetime.datetime.now() + datetime.timedelta(seconds=300)
            self.jobs[id] = MockJob(id, trigger_details)

        def remove_job(self, job_id):
            logger.info(f"(MockScheduler) remove_job: id={job_id}")
            if job_id in self.jobs: del self.jobs[job_id]
        def get_jobs(self): return list(self.jobs.values())
        def running(self): return True

    mock_scheduler_instance = MockScheduler()
    logger.info("Running schedule_task_reminders with mock scheduler and DB...")
    schedule_task_reminders(mock_scheduler_instance, test_q)

    logger.info("Testing trigger_reminder_action directly...")
    trigger_reminder_action(101, "Test Direct Trigger", test_q)
    if not test_q.empty():
        logger.info(f"Item found in test_q: {test_q.get_nowait()}")

    database_manager.get_all_tasks = original_get_all_tasks
    logger.info("Scheduler_manager.py direct test section finished.")
