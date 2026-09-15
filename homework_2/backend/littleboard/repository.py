"""Storage boundary. A database implementation can replace MemoryRepository.

Implementations must preserve order, return detached values, and make each
mutation atomic (including its state checks). No HTTP dependencies live here.
"""
from copy import deepcopy
from threading import RLock
from typing import Protocol
from uuid import uuid4

from .models import Comment, CommentInput, Status, Task, TaskCreate, TaskUpdate


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


class MemoryRepository:
    def __init__(self, tasks: list[Task] | None = None):
        self._tasks = deepcopy(tasks or [])
        self._lock = RLock()

    def _get(self, task_id: str) -> Task:
        for task in self._tasks:
            if task.id == task_id:
                return task
        raise NotFound('Task not found.')

    def list(self, archived: bool = False, search: str = '', assignee: str = '', priority: str = '') -> list[Task]:
        with self._lock:
            return deepcopy([
                t for t in self._tasks if t.archived == archived
                and search.strip().lower() in t.title.lower()
                and (not assignee or t.assignee == assignee)
                and (not priority or t.priority == priority)
            ])

    def create(self, fields: TaskCreate) -> Task:
        with self._lock:
            task = Task(id=str(uuid4()), **fields.model_dump())
            self._tasks.append(task)
            return deepcopy(task)

    def update(self, task_id: str, fields: TaskUpdate) -> Task:
        with self._lock:
            task = self._get(task_id)
            updated = Task.model_validate({**task.model_dump(), **fields.model_dump(exclude_unset=True)})
            if updated.archived and updated.status != 'Done':
                raise Conflict('Archived tasks must remain Done.')
            self._tasks[self._tasks.index(task)] = updated
            return deepcopy(updated)

    def remove(self, task_id: str) -> bool:
        with self._lock:
            self._tasks.remove(self._get(task_id))
            return True

    def move(self, task_id: str, status: Status, before_id: str | None = None) -> Task:
        with self._lock:
            task = self._get(task_id)
            if task.archived:
                raise Conflict('Cannot move this task.')
            if before_id == task_id:
                return deepcopy(task)
            before = self._get(before_id) if before_id is not None else None
            if before and (before.archived or before.status != status):
                raise Conflict('Invalid drop target.')
            self._tasks.remove(task)
            task.status = status
            index = self._tasks.index(before) if before else len(self._tasks)
            self._tasks.insert(index, task)
            return deepcopy(task)

    def archive(self, task_id: str, archived: bool = True) -> Task:
        with self._lock:
            task = self._get(task_id)
            if task.status != 'Done':
                raise Conflict('Only completed tasks can be archived.')
            task.archived = archived
            return deepcopy(task)

    def save_comment(self, task_id: str, fields: CommentInput, comment_id: str | None = None) -> Task:
        with self._lock:
            task = self._get(task_id)
            if comment_id is None:
                task.comments.append(Comment(id=str(uuid4()), **fields.model_dump()))
            else:
                index = next((i for i, c in enumerate(task.comments) if c.id == comment_id), None)
                if index is None:
                    raise NotFound('Comment not found.')
                task.comments[index] = Comment(id=comment_id, **fields.model_dump())
            return deepcopy(task)

    def delete_comment(self, task_id: str, comment_id: str) -> Task:
        with self._lock:
            task = self._get(task_id)
            task.comments = [c for c in task.comments if c.id != comment_id]
            return deepcopy(task)
