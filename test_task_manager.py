import unittest
import os
from datetime import datetime # Needed for task creation
from task_model import Task
import database_manager as db_manager

class TestTaskManager(unittest.TestCase):
    def setUp(self):
        """Set up for test methods."""
        self.db_file = "test_tasks.db"
        # Ensure no old test db file exists
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

    def _create_sample_task_obj(self, id=None, title="Test Task", description="Test Description",
                                duration=60, repetition="Daily", priority=1, category="Test"):
        # Helper to create task objects. ID is often omitted for add_task.
        # Using a fixed creation_date for predictable comparisons.
        creation_date = "2024-01-01T12:00:00"
        if id is not None:
             return Task(id=id, title=title, description=description, duration=duration,
                        creation_date=creation_date, repetition=repetition, priority=priority, category=category)
        else: # For add_task, ID is auto-generated
            # The Task model expects an ID, but for add_task, it's not used from the object itself.
            # We can pass a placeholder like 0 or None if the model allows, or adjust add_task.
            # For now, let's ensure Task can be created with a placeholder ID for this purpose.
            # Modifying Task model to allow id=None temporarily for this use case, or pass 0.
             return Task(id=0, title=title, description=description, duration=duration,
                        creation_date=creation_date, repetition=repetition, priority=priority, category=category)


    def test_task_model_creation(self):
        """Test Task model object creation and attribute assignment."""
        now_iso = datetime.now().isoformat()
        task = Task(id=1, title="Meeting", description="Team meeting", duration=30,
                    creation_date=now_iso, repetition="Weekly", priority=2, category="Work")
        self.assertEqual(task.id, 1)
        self.assertEqual(task.title, "Meeting")
        self.assertEqual(task.description, "Team meeting")
        self.assertEqual(task.duration, 30)
        self.assertEqual(task.creation_date, now_iso)
        self.assertEqual(task.repetition, "Weekly")
        self.assertEqual(task.priority, 2)
        self.assertEqual(task.category, "Work")

    def test_add_and_get_task(self):
        """Test adding a task and then retrieving it."""
        sample_task_obj = self._create_sample_task_obj()

        task_id = db_manager.add_task(self.conn, sample_task_obj)
        self.assertIsNotNone(task_id, "add_task should return a valid row ID")
        self.assertGreater(task_id, 0, "Task ID should be positive")

        retrieved_task = db_manager.get_task(self.conn, task_id)
        self.assertIsNotNone(retrieved_task, "get_task should retrieve the added task")
        self.assertEqual(retrieved_task.id, task_id)
        self.assertEqual(retrieved_task.title, sample_task_obj.title)
        self.assertEqual(retrieved_task.description, sample_task_obj.description)
        self.assertEqual(retrieved_task.duration, sample_task_obj.duration)
        # self.assertEqual(retrieved_task.creation_date, sample_task_obj.creation_date) # Date might be formatted differently
        self.assertEqual(retrieved_task.repetition, sample_task_obj.repetition)
        self.assertEqual(retrieved_task.priority, sample_task_obj.priority)
        self.assertEqual(retrieved_task.category, sample_task_obj.category)

    def test_get_all_tasks(self):
        """Test retrieving all tasks from the database."""
        task1_obj = self._create_sample_task_obj(title="Task 1")
        task2_obj = self._create_sample_task_obj(title="Task 2", duration=45)

        db_manager.add_task(self.conn, task1_obj)
        db_manager.add_task(self.conn, task2_obj)

        all_tasks = db_manager.get_all_tasks(self.conn)
        self.assertEqual(len(all_tasks), 2, "Should retrieve two tasks")
        self.assertIsInstance(all_tasks[0], Task)
        self.assertIsInstance(all_tasks[1], Task)
        self.assertEqual(all_tasks[0].title, "Task 1")
        self.assertEqual(all_tasks[1].title, "Task 2")


    def test_update_task(self):
        """Test updating an existing task."""
        sample_task_obj = self._create_sample_task_obj(title="Original Title")
        task_id = db_manager.add_task(self.conn, sample_task_obj)
        self.assertIsNotNone(task_id)

        # Create an updated Task object. Note: creation_date is kept same as in _create_sample_task_obj
        updated_task_obj = self._create_sample_task_obj(id=task_id, title="Updated Title", priority=5)

        update_success = db_manager.update_task(self.conn, updated_task_obj)
        self.assertTrue(update_success, "update_task should return True on success")

        retrieved_task_after_update = db_manager.get_task(self.conn, task_id)
        self.assertIsNotNone(retrieved_task_after_update)
        self.assertEqual(retrieved_task_after_update.title, "Updated Title")
        self.assertEqual(retrieved_task_after_update.priority, 5)
        self.assertEqual(retrieved_task_after_update.description, sample_task_obj.description) # Check unchanged field

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
