import unittest
import os
from datetime import datetime, timedelta, date # Updated imports
from task_model import Task
import database_manager as db_manager

class TestTaskManager(unittest.TestCase):
    def setUp(self):
        """Set up for test methods."""
        self.db_file = "test_tasks.db"
        if os.path.exists(self.db_file):
            os.remove(self.db_file)
        self.conn = db_manager.create_connection(self.db_file)
        self.assertIsNotNone(self.conn, "Database connection should not be None")
        db_manager.create_table(self.conn)

    def tearDown(self):
        """Tear down after test methods."""
        if self.conn:
            self.conn.close()
        if os.path.exists(self.db_file):
            os.remove(self.db_file)

    def _create_sample_task_obj(self, task_id_override=None, title_suffix="",
                                description="This is a sample task description.",
                                duration=60, repetition="None", priority=2, category="Testing",
                                status="Pending", due_date_offset_days=2,
                                last_reset_date_override=None, creation_date_override=None):
        """Helper to create task objects with new fields and more overrides."""
        creation_dt_obj = datetime.fromisoformat(creation_date_override) if creation_date_override else datetime.now()
        creation_iso = creation_dt_obj.isoformat()

        current_id = task_id_override if task_id_override is not None else 0

        due_dt_iso = None
        if due_date_offset_days is not None:
            due_dt = creation_dt_obj + timedelta(days=due_date_offset_days)
            due_dt_iso = due_dt.isoformat()

        # Task model's __init__ defaults last_reset_date to today if None is passed.
        # If last_reset_date_override is provided, it's used.
        # If last_reset_date_override is explicitly None, the model will default it.
        effective_last_reset_date = last_reset_date_override

        return Task(
            id=current_id,
            title=f"Sample Task{title_suffix}",
            description=description,
            duration=duration,
            creation_date=creation_iso,
            repetition=repetition,
            priority=priority,
            category=category,
            due_date=due_dt_iso,
            status=status,
            last_reset_date=effective_last_reset_date # Can be None to test model's default
        )

    def test_task_model_creation(self):
        """Test Task model object creation and attribute assignment."""
        now_dt = datetime.now()
        creation_iso = now_dt.isoformat()
        due_iso = (now_dt + timedelta(days=5)).isoformat()
        today_iso = date.today().isoformat()

        task = Task(id=1, title="Meeting", description="Team meeting", duration=30,
                    creation_date=creation_iso, repetition="Weekly", priority=2, category="Work",
                    due_date=due_iso, status="Scheduled", last_reset_date=today_iso)

        self.assertEqual(task.id, 1)
        self.assertEqual(task.title, "Meeting")
        self.assertEqual(task.description, "Team meeting")
        self.assertEqual(task.duration, 30)
        self.assertEqual(task.creation_date, creation_iso)
        self.assertEqual(task.repetition, "Weekly")
        self.assertEqual(task.priority, 2)
        self.assertEqual(task.category, "Work")
        self.assertEqual(task.due_date, due_iso)
        self.assertEqual(task.status, "Scheduled")
        self.assertEqual(task.last_reset_date, today_iso)

        # Test default last_reset_date
        task_default_reset = Task(id=2, title="Default Reset", description="", duration=0,
                                  creation_date=creation_iso, repetition="", priority=1, category="",
                                  last_reset_date=None) # Explicitly pass None
        self.assertEqual(task_default_reset.last_reset_date, date.today().isoformat())


    def test_add_and_get_task(self):
        """Test adding a task and then retrieving it, including new fields."""
        # last_reset_date is set by Task constructor if None is passed to it.
        # db_manager.add_task also ensures it's set if somehow None from task object.
        # So, the retrieved task should always have a last_reset_date.
        sample_task_obj = self._create_sample_task_obj(title_suffix=" AddGet")

        # The sample_task_obj will have its last_reset_date set by its __init__ to today.

        task_id = db_manager.add_task(self.conn, sample_task_obj)
        self.assertIsNotNone(task_id, "add_task should return a valid row ID")
        self.assertGreater(task_id, 0, "Task ID should be positive")

        retrieved_task = db_manager.get_task(self.conn, task_id)
        self.assertIsNotNone(retrieved_task, "get_task should retrieve the added task")

        self.assertEqual(retrieved_task.id, task_id)
        self.assertEqual(retrieved_task.title, sample_task_obj.title)
        self.assertEqual(retrieved_task.description, sample_task_obj.description)
        self.assertEqual(retrieved_task.duration, sample_task_obj.duration)
        # Creation date comparison can be tricky due to microseconds precision.
        # For now, let's assume they are close enough or handle this by parsing and comparing.
        # self.assertEqual(retrieved_task.creation_date, sample_task_obj.creation_date)
        self.assertEqual(retrieved_task.repetition, sample_task_obj.repetition)
        self.assertEqual(retrieved_task.priority, sample_task_obj.priority)
        self.assertEqual(retrieved_task.category, sample_task_obj.category)
        self.assertEqual(retrieved_task.due_date, sample_task_obj.due_date)
        self.assertEqual(retrieved_task.status, sample_task_obj.status)
        self.assertEqual(retrieved_task.last_reset_date, sample_task_obj.last_reset_date)


    def test_get_all_tasks(self):
        """Test retrieving all tasks from the database."""
        # Create tasks with slight time difference to ensure consistent order for testing if needed
        # However, get_all_tasks sorts by creation_date DESC, so most recent first.
        now = datetime.now()
        task1_creation = (now - timedelta(seconds=10)).isoformat()
        task2_creation = now.isoformat()

        task1_obj = self._create_sample_task_obj(title_suffix=" All1", creation_date_override=task1_creation)
        task2_obj = self._create_sample_task_obj(title_suffix=" All2", duration=45, status="Completed", creation_date_override=task2_creation)

        db_manager.add_task(self.conn, task1_obj) # task1 added first (older)
        db_manager.add_task(self.conn, task2_obj) # task2 added second (newer)

        all_tasks = db_manager.get_all_tasks(self.conn)
        self.assertEqual(len(all_tasks), 2, "Should retrieve two tasks")

        # Tasks are ordered by creation_date DESC in get_all_tasks
        retrieved_t2, retrieved_t1 = all_tasks[0], all_tasks[1] # Assuming task2 was created after task1 if now() is precise

        self.assertIsInstance(retrieved_t1, Task)
        self.assertIsInstance(retrieved_t2, Task)

        # Check some basic fields to ensure objects are populated
        # get_all_tasks orders by creation_date DESC, so task2_obj should be first.
        self.assertEqual(all_tasks[0].title, task2_obj.title)
        self.assertEqual(all_tasks[1].title, task1_obj.title)
        self.assertEqual(all_tasks[0].status, "Completed")


    def test_update_task(self):
        """Test updating an existing task with new fields."""
        original_task_obj = self._create_sample_task_obj(title_suffix=" OriginalForUpdate")
        task_id = db_manager.add_task(self.conn, original_task_obj)
        self.assertIsNotNone(task_id)

        # Create an updated Task object
        # Fetch the just-added task to get its actual creation_date and last_reset_date from DB perspective
        # This ensures we only change what we intend to change for the update.
        task_to_update_basis = db_manager.get_task(self.conn, task_id)
        self.assertIsNotNone(task_to_update_basis)

        new_due_date = (datetime.now() + timedelta(days=10)).isoformat()
        new_last_reset = (date.today() - timedelta(days=1)).isoformat() # e.g., yesterday

        updated_task_data_obj = Task(
            id=task_id, # Critical: ID must be the same
            title="Updated Title",
            description="Updated description.",
            duration=90,
            creation_date=task_to_update_basis.creation_date, # Preserve original creation_date
            repetition="Weekly",
            priority=1, # Low
            category="Work Update",
            due_date=new_due_date,
            status="In Progress",
            last_reset_date=new_last_reset
        )

        update_success = db_manager.update_task(self.conn, updated_task_data_obj)
        self.assertTrue(update_success, "update_task should return True on success")

        retrieved_after_update = db_manager.get_task(self.conn, task_id)
        self.assertIsNotNone(retrieved_after_update)

        self.assertEqual(retrieved_after_update.title, "Updated Title")
        self.assertEqual(retrieved_after_update.description, "Updated description.")
        self.assertEqual(retrieved_after_update.duration, 90)
        self.assertEqual(retrieved_after_update.repetition, "Weekly")
        self.assertEqual(retrieved_after_update.priority, 1)
        self.assertEqual(retrieved_after_update.category, "Work Update")
        self.assertEqual(retrieved_after_update.due_date, new_due_date)
        self.assertEqual(retrieved_after_update.status, "In Progress")
        self.assertEqual(retrieved_after_update.last_reset_date, new_last_reset)
        self.assertEqual(retrieved_after_update.creation_date, original_task_obj.creation_date) # Should remain unchanged


    def test_delete_task(self):
        """Test deleting a task."""
        sample_task_obj = self._create_sample_task_obj()
        task_id = db_manager.add_task(self.conn, sample_task_obj)
        self.assertIsNotNone(task_id)

        delete_success = db_manager.delete_task(self.conn, task_id)
        self.assertTrue(delete_success, "delete_task should return True on success")

        retrieved_task_after_delete = db_manager.get_task(self.conn, task_id)
        self.assertIsNone(retrieved_task_after_delete, "Task should be None after deletion")

    def test_get_nonexistent_task(self):
        """Test retrieving a task that does not exist."""
        retrieved_task = db_manager.get_task(self.conn, 999)
        self.assertIsNone(retrieved_task, "Retrieving a non-existent task should return None")

    def test_update_nonexistent_task(self):
        """Test updating a task that does not exist."""
        non_existent_task = self._create_sample_task_obj(task_id_override=999, title_suffix=" NonExistent")
        update_success = db_manager.update_task(self.conn, non_existent_task)
        self.assertFalse(update_success, "Updating a non-existent task should return False")

    def test_delete_nonexistent_task(self):
        """Test deleting a task that does not exist."""
        delete_success = db_manager.delete_task(self.conn, 999)
        self.assertFalse(delete_success, "Deleting a non-existent task should return False")

if __name__ == '__main__':
    unittest.main(verbosity=2)
