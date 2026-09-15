"""Storage boundary shared by the API and SQLAlchemy implementation.

Implementations must preserve order, return detached values, and make each
mutation atomic (including its state checks). No HTTP dependencies live here.
"""
from typing import Protocol

from .models import CommentInput, Status, Task, TaskCreate, TaskUpdate


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class TaskRepository(Protocol):
    def list(self, archived: bool, search: str, assignee: str, priority: str) -> list[Task]: ...
    def create(self, fields: TaskCreate) -> Task: ...
    def update(self, task_id: str, fields: TaskUpdate) -> Task: ...
    def remove(self, task_id: str) -> bool: ...
    def move(self, task_id: str, status: Status, before_id: str | None) -> Task: ...
    def archive(self, task_id: str, archived: bool) -> Task: ...
    def save_comment(self, task_id: str, fields: CommentInput, comment_id: str | None = None) -> Task: ...
    def delete_comment(self, task_id: str, comment_id: str) -> Task: ...
