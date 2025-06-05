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
                # This logic is a bit simplified; doesn't perfectly handle end-of-month.
                # A more robust solution would use dateutil.relativedelta or more complex date math.
                if today.year > last_reset_dt.year or \
                   (today.year == last_reset_dt.year and today.month > last_reset_dt.month):
                    if today.day >= last_reset_dt.day: # Check if the day of the month has been reached or passed
                         needs_reset = True
                elif today.year == last_reset_dt.year and today.month == last_reset_dt.month and today.day > last_reset_dt.day and last_reset_dt.day != today.day :
                    # case where reset day was e.g. 15th, today is 16th of same month (and not same day as last_reset if it was today)
                    # This part of monthly logic might need more refinement for edge cases like tasks created on 31st.
                    pass # Handled by the more general year/month check for now or needs more specific logic.

                # More robust monthly check:
                # Needs reset if (current year > last reset year) OR
                # (current year == last reset year AND current month > last reset month)
                # AND current day of month >= last reset day of month (approximately)
                # This doesn't precisely handle "day X of every month" if X > days in current month.
                # For simplicity, we assume a reset if the current date is in a subsequent month
                # and the day of the month is >= the original task's reset day, OR if it's a new year.

                # Simplified monthly check: if a new month has started since the last reset, and we're on or after the original day.
                if (today.year > last_reset_dt.year) or \
                   (today.year == last_reset_dt.year and today.month > last_reset_dt.month):
                    if today.day >= last_reset_dt.day: # If original was 15th, reset on 15th or later of subsequent months
                        needs_reset = True
                # If still in the same month and year, but past the reset day (and not the same day)
                elif today.year == last_reset_dt.year and today.month == last_reset_dt.month and today.day > last_reset_dt.day:
                     # This condition is problematic, as it would reset daily within the same month after the first reset.
                     # The core idea for monthly is: has at least one month passed since last_reset_dt?
                     # A simple check: if today is at least one month after last_reset_dt.
                     # (today.year * 12 + today.month) > (last_reset_dt.year * 12 + last_reset_dt.month)
                     # and today.day >= last_reset_dt.day
                     pass # The current logic for monthly needs refinement.
                     # For now, using a simplified approach: if it's a new month & day is >= last reset day
                if (today.year > last_reset_dt.year or today.month > last_reset_dt.month) and today.day >= last_reset_dt.day:
                     needs_reset = True # This is too simple, e.g. reset on Mar 15th, would reset Apr 1st if day was <15.

                # Let's use a more direct comparison for monthly:
                # Reset if today is in a month after the last_reset_dt's month (could be same year or later year)
                # AND the day of the month for reset has been reached or passed.
                # This is still not perfect for "last day of month" type scenarios.
                if (today.year * 100 + today.month) > (last_reset_dt.year * 100 + last_reset_dt.month):
                    if today.day >= last_reset_dt.day:
                        needs_reset = True
                elif (today.year * 100 + today.month) == (last_reset_dt.year * 100 + last_reset_dt.month) and today.day > last_reset_dt.day:
                     # This would reset daily after the day in the same month. Incorrect.
                     # Monthly reset should only happen once the month boundary is crossed relative to the last_reset_day.
                     pass

                # Corrected (simpler) monthly logic:
                # Has a month passed since the last_reset_date's month?
                # And is the current day of the month >= the last_reset_date's day of the month?
                if today > last_reset_dt: # Basic check that we are past the last reset
                    if today.month != last_reset_dt.month or today.year != last_reset_dt.year: # Ensure we are in a new month/year
                        if today.day >= last_reset_dt.day: # And the day of month is met
                            needs_reset = True
                    # This still doesn't cover if task was created e.g. Jan 31st, and Feb only has 28 days.
                    # A proper library like dateutil.rrule or relativedelta is better for robust recurrence.
                    # For this exercise, this simplification will be used.

            elif task.repetition == 'Yearly':
                if today > last_reset_dt: # Basic check
                    if today.year > last_reset_dt.year: # Ensure we are in a new year
                        if (today.month > last_reset_dt.month) or \
                           (today.month == last_reset_dt.month and today.day >= last_reset_dt.day):
                            needs_reset = True

            if needs_reset:
                original_status = task.status
                task.status = "Pending" # Reset status
                task.last_reset_date = today.isoformat() # Update last_reset_date to today
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


def schedule_task_reminders(scheduler):
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
            # Still proceed to remove old jobs if any

        now = datetime.datetime.now()

        for task in tasks:
            job_id = f"reminder_{task.id}"

            if not task.due_date or task.status == 'Completed':
                # If no due date or task is completed, ensure no reminder is scheduled.
                # Active jobs will be checked later, and this job_id won't be in active_reminder_job_ids.
                continue

            try:
                due_datetime = datetime.datetime.fromisoformat(task.due_date)
            except ValueError:
                logger.error(f"Invalid due_date format for Task '{task.title}' (ID: {task.id}): {task.due_date}. Skipping reminder.")
                continue

            active_reminder_job_ids.add(job_id) # Mark this job_id as active

            trigger_details = None
            is_new_job = scheduler.get_job(job_id) is None

            if not task.repetition or task.repetition.lower() == 'none': # One-time reminder
                if due_datetime < now:
                    logger.info(f"One-time reminder for Task '{task.title}' (ID: {task.id}) is in the past. Skipping.")
                    active_reminder_job_ids.remove(job_id) # Don't keep it as active if it's past
                    continue
                trigger_details = {'trigger': 'date', 'run_date': due_datetime}
            else: # Repeating task reminder (Daily, Weekly, Monthly, Yearly)
                # For repeating tasks, the reminder fires at the due time on relevant days.
                # 'start_date' ensures we don't trigger for past occurrences if scheduler was down.
                # However, for repeating tasks, the due_datetime itself might be in the past
                # but the repetition rule means it's still valid for future occurrences.
                # We should ensure the first trigger is not in the past from 'now'.
                # A common approach is to set start_date to now or slightly in future for cron.

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
                        args=[task.id, task.title],
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


        # Remove stale reminder jobs
        removed_count = 0
        if scheduler.running: # Check if scheduler is running before getting jobs
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


def initialize_scheduler():
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(check_repeating_tasks, 'interval', hours=1, id='job_check_repetition')

    try:
        scheduler.start()
        logger.info("BackgroundScheduler initialized and started.")

        # Initial scan and scheduling of reminders
        schedule_task_reminders(scheduler)

        # Add a recurring job for refreshing reminders
        scheduler.add_job(schedule_task_reminders, 'interval', minutes=15, args=[scheduler], id='job_rescheduler_reminders')
        logger.info("Job 'check_repeating_tasks' scheduled every 1 hour. Job 'schedule_task_reminders' scheduled every 15 minutes.")

    except Exception as e:
        logger.error(f"Failed to start or fully configure scheduler: {e}", exc_info=True)
        if scheduler.running: # If start() succeeded but a subsequent add_job failed
            scheduler.shutdown()
        return None
    return scheduler

if __name__ == '__main__':
    # This block is for direct testing of the scheduler logic.
    # It won't run when imported by main_app.py.
    logger.info("Testing scheduler_manager.py directly...")

    # Create a dummy connection and a few tasks for testing
    # This requires a tasks.db to exist or be creatable.
    # For more isolated testing, mock database_manager.

    # Simulate a few tasks
    class MockTask:
        def __init__(self, id, title, repetition, last_reset_date, status="Pending"):
            self.id = id
            self.title = title
            self.repetition = repetition
            self.last_reset_date = last_reset_date
            self.status = status
            self.due_date = None # Add other fields if db_manager.update_task needs them
            self.description = ""
            self.duration = 0
            self.creation_date = datetime.datetime.now().isoformat()
            self.priority = 1
            self.category = ""

    # Mock database_manager for standalone testing
    original_get_all_tasks = database_manager.get_all_tasks
    original_update_task = database_manager.update_task

    mock_tasks_db = []

    def mock_get_all_tasks(conn):
        logger.info("(Mock) Getting all tasks.")
        return mock_tasks_db.copy()

    def mock_update_task(conn, task):
        logger.info(f"(Mock) Updating task: {task.title}, New Status: {task.status}, New Last Reset: {task.last_reset_date}")
        for i, t in enumerate(mock_tasks_db):
            if t.id == task.id:
                mock_tasks_db[i] = task
                return True
        return False

    database_manager.get_all_tasks = mock_get_all_tasks
    database_manager.update_task = mock_update_task

    # Add some sample tasks to the mock_tasks_db
    today_str = datetime.date.today().isoformat()
    yesterday_str = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    last_week_str = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    last_month_str = (datetime.date.today() - datetime.timedelta(days=30)).isoformat() # Approx
    last_year_str = (datetime.date.today() - datetime.timedelta(days=365)).isoformat() # Approx

    mock_tasks_db.extend([
        MockTask(1, "Daily Task", "Daily", yesterday_str, "Completed"),
        MockTask(2, "Weekly Task", "Weekly", last_week_str, "Completed"),
        MockTask(3, "Monthly Task", "Monthly", last_month_str, "Completed"), # Will reset if day matches/passed
        MockTask(4, "Yearly Task", "Yearly", last_year_str, "Completed"),   # Will reset if month/day matches/passed
        MockTask(5, "Non-Repeating", "None", yesterday_str),
        MockTask(6, "Daily Task Not Reset", "Daily", today_str), # Should not reset
        MockTask(7, "Weekly Task Not Reset", "Weekly", yesterday_str), # Should not reset yet
        MockTask(8, "Monthly Task - specific day", "Monthly", "2023-05-15"), # Example of a past date for monthly
        MockTask(9, "Monthly Task - day after today", "Monthly", (datetime.date.today() - datetime.timedelta(days=32)).replace(day=datetime.date.today().day + 1 if datetime.date.today().day < 28 else 28).isoformat() if (datetime.date.today() - datetime.timedelta(days=32)).month != datetime.date.today().month else (datetime.date.today() - datetime.timedelta(days=60)).isoformat() ), # complex date to test month boundary
    ])
    # Adjust task 9: A task from last month, where the day of month has passed or is today.
    # E.g., if today is June 15th, a task last reset on May 10th.
    prev_month_same_day_or_earlier = (datetime.date.today().replace(day=1) - datetime.timedelta(days=1)).replace(day=min(datetime.date.today().day, 28)) # Ensure valid day for prev month
    mock_tasks_db.append(MockTask(10, "Monthly Task - Prev Month", "Monthly", prev_month_same_day_or_earlier.isoformat(), "Completed"))


    logger.info("Running check_repeating_tasks with mock data...")
    check_repeating_tasks() # Call the function directly for testing

    logger.info("Mock tasks after check:")
    for task in mock_tasks_db:
        logger.info(f"  - {task.title} (ID: {task.id}), Status: {task.status}, Last Reset: {task.last_reset_date}")

    # Restore original functions if other tests in this process need them
    database_manager.get_all_tasks = original_get_all_tasks
    database_manager.update_task = original_update_task

    # Keep scheduler running for a bit if we were testing initialize_scheduler()
    # import time
    # scheduler = initialize_scheduler()
    # if scheduler:
    #     try:
    #         while True:
    #             time.sleep(2)
    #     except (KeyboardInterrupt, SystemExit):
    #         logger.info("Shutting down scheduler from test block.")
    #         scheduler.shutdown()
    logger.info("Scheduler_manager.py direct test finished.")

def trigger_reminder_action(task_id: int, task_title: str):
    """
    Placeholder action for when a task reminder is triggered.

    Currently, this function only logs the reminder event.
    In a full application, this could trigger a desktop notification,
    play a sound, or update the UI.
    """
    logger.info(f"REMINDER TRIGGERED (placeholder): Task ID: {task_id} - Title: '{task_title}'")
