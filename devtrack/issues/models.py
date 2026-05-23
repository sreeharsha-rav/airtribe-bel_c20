from abc import ABC, abstractmethod
from datetime import datetime

class BaseEntity(ABC):
    @abstractmethod
    def validate(self):
        pass

    def to_dict(self):
        return {
            key: value
            for key, value in self.__dict__.items()
        }

class Reporter(BaseEntity):
    def __init__(self, name, email):
        self.name = name
        self.email = email

    def validate(self):
        if not self.name or not self.name.strip():
            raise ValueError('Name cannot be empty')
        if not self.email or '@' not in self.email:
            raise ValueError('Invalid email')

class Issue(BaseEntity):
    STATUS_CHOICES = ['open', 'in_progress', 'resolved', 'closed']
    PRIORITY_CHOICES = ['low', 'medium', 'high', 'critical']

    def __init__(self, title, description, status, priority, reporter, created_at=None):
        self.title = title
        self.description = description
        self.status = status
        self.priority = priority
        self.reporter = reporter
        self.created_at = created_at if created_at is not None else datetime.now()

    def validate(self):
        if not self.title or not self.title.strip():
            raise ValueError('Title cannot be empty or whitespace-only')
        if self.status not in self.STATUS_CHOICES:
            raise ValueError('Invalid status')
        if self.priority not in self.PRIORITY_CHOICES:
            raise ValueError('Invalid priority')

    def describe(self):
        return f"{self.title} [{self.priority}]"

class CriticalIssue(Issue):
    def describe(self):
        return f"[URGENT] {self.title} — needs immediate attention"

class LowPriorityIssue(Issue):
    def describe(self):
        return f"{self.title} — low priority, handle when free"
