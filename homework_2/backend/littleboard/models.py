import re
from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

Status = Literal['Backlog', 'To Do', 'In Progress', 'Done']
Priority = Literal['Low', 'Medium', 'High']
Assignee = Literal['Alex Morgan', 'Jamie Chen', 'Sam Rivera', 'Taylor Brooks']
OptionalAssignee = Literal['', 'Alex Morgan', 'Jamie Chen', 'Sam Rivera', 'Taylor Brooks']
PriorityFilter = Literal['', 'Low', 'Medium', 'High']
NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r'\S')]


def valid_due_date(value: str) -> str:
    if value:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('Use YYYY-MM-DD for due dates.')
        date.fromisoformat(value)
    return value


DueDate = Annotated[str, AfterValidator(valid_due_date), Field(json_schema_extra={
    'oneOf': [{'type': 'string', 'const': ''},
              {'type': 'string', 'format': 'date', 'pattern': r'^\d{4}-\d{2}-\d{2}$'}],
})]


class Error(BaseModel):
    detail: str


class InputModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class TaskCreate(InputModel):
    title: NonBlankText
    status: Status
    priority: Priority
    description: str = ''
    assignee: OptionalAssignee = ''
    dueDate: DueDate = ''


class TaskUpdate(InputModel):
    # Defaults allow omission; exclude_unset keeps them out of PATCH writes.
    # Explicit null still fails because every field has a non-nullable type.
    title: NonBlankText = ''
    status: Status = 'Backlog'
    priority: Priority = 'Medium'
    description: str = ''
    assignee: OptionalAssignee = ''
    dueDate: DueDate = ''


class CommentInput(InputModel):
    name: Assignee
    text: NonBlankText


class Comment(CommentInput):
    id: str


class Task(TaskCreate):
    id: str
    archived: bool = False
    comments: list[Comment] = Field(default_factory=list)


class MoveInput(InputModel):
    status: Status
    beforeId: Annotated[str, Field(min_length=1)] | None = None


class ArchiveInput(InputModel):
    archived: bool = True
