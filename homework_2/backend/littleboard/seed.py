from datetime import date, timedelta

from .models import Comment, Task


def demo_tasks() -> list[Task]:
    rows = [
        ('Explore onboarding ideas', 'Backlog', 'Low', 'Jamie Chen', None),
        ('Review accessibility checklist', 'Backlog', 'Medium', 'Sam Rivera', 5),
        ('Write the welcome copy', 'To Do', 'Medium', 'Taylor Brooks', 2),
        ('Define the project scope', 'To Do', 'High', 'Alex Morgan', -2),
        ('Sketch the mobile layout', 'To Do', 'Low', '', 4),
        ('Build the task board', 'In Progress', 'High', 'Alex Morgan', 1),
        ('Design task details', 'In Progress', 'Medium', 'Jamie Chen', 3),
        ('Gather team feedback', 'Done', 'Medium', 'Sam Rivera', -1),
        ('Set up the workspace', 'Done', 'Low', 'Taylor Brooks', None),
        ('Project kickoff', 'Done', 'Low', 'Alex Morgan', -7),
    ]
    return [Task(
        id=f'task-{i + 1}', title=title, description=f'Demo task: {title}.',
        status=status, priority=priority, assignee=assignee,
        dueDate='' if offset is None else (date.today() + timedelta(days=offset)).isoformat(),
        archived=i == 9,
        comments=[Comment(id='comment-1', name='Jamie Chen', text='The first sketches are ready.')]
        if i == 5 else [],
    ) for i, (title, status, priority, assignee, offset) in enumerate(rows)]
