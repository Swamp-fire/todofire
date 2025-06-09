from typing import Union

class Task:
    def __init__(self,
                 id: int,
                 title: str,
                 description: str,
                 duration: int,
                 creation_date: str,
                 repetition: str,
                 priority: int,
                 category: str,
                 due_date: Union[str, None] = None,
                 reminder_set: bool = False,
                 status: str = "Pending"):
        self.id: int = id
        self.title: str = title
        self.description: str = description
        self.duration: int = duration
        self.creation_date: str = creation_date  # ISO format string
        self.repetition: str = repetition
        self.priority: int = priority
        self.category: str = category
        self.due_date: Union[str, None] = due_date
        self.reminder_set: bool = reminder_set
        self.status: str = status  # e.g., "Pending", "Completed"
