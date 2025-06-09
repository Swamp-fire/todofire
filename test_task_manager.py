import unittest
import os
from datetime import datetime # Needed for task creation
from task_model import Task
import database_manager as db_manager

class TestTaskManager(unittest.TestCase):
    def setUp(self):
        """Set up for test methods."""
        self.conn = db_manager.create_connection(":memory:") # Use in-memory database
        self.assertIsNotNone(self.conn, "Database connection should not be None")
        db_manager.create_table(self.conn)

    def tearDown(self):
        """Tear down after test methods."""
        if self.conn:
            self.conn.close()
        # No need to remove db_file if it's in-memory

    def _create_sample_task_obj(self, id=None, title="Test Task", description="Test Description",
                                duration=60, repetition="Daily", priority=1, category="Test",
                                due_date=None, reminder_set=False, status="Pending"):
        # Helper to create task objects.
        creation_date = datetime.now().isoformat() # Use current time for creation_date for flexibility

        # Ensure due_date is also a string if provided, or None
        if due_date is not None and not isinstance(due_date, str):
            due_date = due_date.isoformat()

        if id is not None:
             return Task(id=id, title=title, description=description, duration=duration,
                        creation_date=creation_date, repetition=repetition, priority=priority, category=category,
                        due_date=due_date, reminder_set=reminder_set, status=status)
        else:
             return Task(id=0, title=title, description=description, duration=duration, # id=0 as placeholder for add_task
                        creation_date=creation_date, repetition=repetition, priority=priority, category=category,
                        due_date=due_date, reminder_set=reminder_set, status=status)


    def test_task_model_creation(self):
        """Test Task model object creation and attribute assignment."""
        now_iso = datetime.now().isoformat()
        due_later_iso = (datetime.now() + datetime.timedelta(days=1)).isoformat()
        task = Task(id=1, title="Meeting", description="Team meeting", duration=30,
                    creation_date=now_iso, repetition="Weekly", priority=2, category="Work",
                    due_date=due_later_iso, reminder_set=True, status="Urgent")
        self.assertEqual(task.id, 1)
        self.assertEqual(task.title, "Meeting")
        self.assertEqual(task.description, "Team meeting")
        self.assertEqual(task.duration, 30)
        self.assertEqual(task.creation_date, now_iso)
        self.assertEqual(task.repetition, "Weekly")
        self.assertEqual(task.priority, 2)
        self.assertEqual(task.category, "Work")
        self.assertEqual(task.due_date, due_later_iso)
        self.assertTrue(task.reminder_set)
        self.assertEqual(task.status, "Urgent")

    def test_task_model_new_fields_defaults(self):
        """Test Task model default values for new fields."""
        now_iso = datetime.now().isoformat()
        # Create task without specifying due_date, reminder_set, status
        task_default = Task(id=2, title="Default Test", description="Desc", duration=10,
                            creation_date=now_iso, repetition="None", priority=1, category="Defaults")
        self.assertIsNone(task_default.due_date, "Default due_date should be None")
        self.assertFalse(task_default.reminder_set, "Default reminder_set should be False")
        self.assertEqual(task_default.status, "Pending", "Default status should be 'Pending'")


    def test_add_and_get_task_with_all_fields(self):
        """Test adding a task with all fields and then retrieving it."""
        now = datetime.now()
        due_date_iso = (now + datetime.timedelta(days=1)).isoformat()
        # creation_date_iso is handled by _create_sample_task_obj

        task_data = self._create_sample_task_obj(
            title="Full Task", description="Test Desc", duration=60,
            repetition="Daily", priority=3, category="Work",
            due_date=due_date_iso, reminder_set=True, status="Scheduled"
        )

        task_id = db_manager.add_task(self.conn, task_data)
        self.assertIsNotNone(task_id, "add_task should return a valid row ID")

        retrieved_task = db_manager.get_task(self.conn, task_id)
        self.assertIsNotNone(retrieved_task)
        self.assertEqual(retrieved_task.title, "Full Task")
        self.assertEqual(retrieved_task.description, "Test Desc")
        self.assertEqual(retrieved_task.duration, 60)
        self.assertEqual(retrieved_task.repetition, "Daily")
        self.assertEqual(retrieved_task.priority, 3)
        self.assertEqual(retrieved_task.category, "Work")
        self.assertEqual(retrieved_task.due_date, due_date_iso)
        self.assertTrue(retrieved_task.reminder_set)
        self.assertEqual(retrieved_task.status, "Scheduled")

    def test_get_all_tasks_includes_new_fields(self):
        """Test retrieving all tasks, ensuring new fields are present."""
        due_date1 = datetime.now() + datetime.timedelta(days=1)
        due_date2 = datetime.now() + datetime.timedelta(days=2)

        task1_obj = self._create_sample_task_obj(title="AllFields Task 1", status="StatusA",
                                                 due_date=due_date1, reminder_set=True)
        task2_obj = self._create_sample_task_obj(title="AllFields Task 2", status="StatusB",
                                                 due_date=due_date2, reminder_set=False)

        db_manager.add_task(self.conn, task1_obj)
        db_manager.add_task(self.conn, task2_obj)

        all_tasks = db_manager.get_all_tasks(self.conn)
        self.assertEqual(len(all_tasks), 2)

        retrieved_task1 = next(t for t in all_tasks if t.title == "AllFields Task 1")
        retrieved_task2 = next(t for t in all_tasks if t.title == "AllFields Task 2")

        self.assertEqual(retrieved_task1.status, "StatusA")
        self.assertTrue(retrieved_task1.reminder_set)
        self.assertEqual(retrieved_task1.due_date, due_date1.isoformat())

        self.assertEqual(retrieved_task2.status, "StatusB")
        self.assertFalse(retrieved_task2.reminder_set)
        self.assertEqual(retrieved_task2.due_date, due_date2.isoformat())

    def test_update_task_new_fields(self):
        """Test updating due_date, reminder_set, and status of an existing task."""
        initial_due_date = datetime.now() + datetime.timedelta(days=1)
        sample_task_obj = self._create_sample_task_obj(
            title="Update Test Task",
            due_date=initial_due_date,
            reminder_set=True,
            status="InitialStatus"
        )
        task_id = db_manager.add_task(self.conn, sample_task_obj)
        self.assertIsNotNone(task_id)

        retrieved_task = db_manager.get_task(self.conn, task_id) # Get the task with its assigned ID and creation_date
        self.assertIsNotNone(retrieved_task)

        updated_due_date = datetime.now() + datetime.timedelta(days=2)
        retrieved_task.due_date = updated_due_date.isoformat()
        retrieved_task.reminder_set = False
        retrieved_task.status = "Completed"

        update_success = db_manager.update_task(self.conn, retrieved_task)
        self.assertTrue(update_success)

        updated_retrieved_task = db_manager.get_task(self.conn, task_id)
        self.assertIsNotNone(updated_retrieved_task)
        self.assertEqual(updated_retrieved_task.due_date, updated_due_date.isoformat())
        self.assertFalse(updated_retrieved_task.reminder_set)
        self.assertEqual(updated_retrieved_task.status, "Completed")
        # Ensure other fields didn't change unexpectedly
        self.assertEqual(updated_retrieved_task.title, "Update Test Task")


    def test_process_task_action_db_logic(self):
        """Test simulating ReminderPopup._process_task_action database changes."""
        now = datetime.now()
        due_date_iso = now.isoformat()

        # Test case 1: Simulating "Complete" action
        task_data_complete = self._create_sample_task_obj(
            title="Action Complete Test", due_date=due_date_iso, reminder_set=True, status="Pending"
        )
        task_id_complete = db_manager.add_task(self.conn, task_data_complete)

        task_to_update_complete = db_manager.get_task(self.conn, task_id_complete)
        self.assertIsNotNone(task_to_update_complete)
        task_to_update_complete.reminder_set = False
        task_to_update_complete.status = "Completed"
        db_manager.update_task(self.conn, task_to_update_complete)

        processed_complete_task = db_manager.get_task(self.conn, task_id_complete)
        self.assertFalse(processed_complete_task.reminder_set)
        self.assertEqual(processed_complete_task.status, "Completed")

        # Test case 2: Simulating "Skip" action (no status change)
        task_data_skip = self._create_sample_task_obj(
            title="Action Skip Test", due_date=due_date_iso, reminder_set=True, status="Pending"
        )
        task_id_skip = db_manager.add_task(self.conn, task_data_skip)

        task_to_update_skip = db_manager.get_task(self.conn, task_id_skip)
        self.assertIsNotNone(task_to_update_skip)
        task_to_update_skip.reminder_set = False
        # No status change for skip
        db_manager.update_task(self.conn, task_to_update_skip)

        processed_skip_task = db_manager.get_task(self.conn, task_id_skip)
        self.assertFalse(processed_skip_task.reminder_set)
        self.assertEqual(processed_skip_task.status, "Pending") # Status remains as it was


    def test_delete_task(self): # Keep this test, it's fundamental
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
        # creation_date from helper ensures it's a valid date string for the model
        non_existent_task = self._create_sample_task_obj(id=999, title="Non Existent")
        update_success = db_manager.update_task(self.conn, non_existent_task)
        self.assertFalse(update_success, "Updating a non-existent task should return False")

    def test_delete_nonexistent_task(self):
        """Test deleting a task that does not exist."""
        delete_success = db_manager.delete_task(self.conn, 999)
        self.assertFalse(delete_success, "Deleting a non-existent task should return False")

if __name__ == '__main__':
    unittest.main(verbosity=2)
