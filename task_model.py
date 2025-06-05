import datetime

class Task:
    def __init__(self, id: int, title: str, description: str, duration: int,
                 creation_date: str, repetition: str, priority: int, category: str,
                 due_date: str = None, status: str = "Pending", last_reset_date: str = None):
        self.id = id
        self.title = title
        self.description = description
        self.duration = duration  # Expected to be total minutes
        self.creation_date = creation_date
        self.repetition = repetition
        self.priority = priority
        self.category = category
        self.due_date = due_date  # ISO datetime string or None
        self.status = status      # E.g., "Pending", "Completed", "Overdue"

        if last_reset_date is None:
            # Default last_reset_date to today's date if not provided
            # This is useful for scheduler logic to know when it was last considered "fresh"
            self.last_reset_date = datetime.date.today().isoformat()
        else:
            self.last_reset_date = last_reset_date # ISO date string or None
