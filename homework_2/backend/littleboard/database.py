from contextlib import contextmanager
from threading import RLock
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, create_engine, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from sqlalchemy.pool import StaticPool

from .models import Comment, Task
from .repository import Conflict, NotFound


class Base(DeclarativeBase):
    pass


class BoardRow(Base):
    __tablename__ = 'board'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    initialized: Mapped[bool] = mapped_column(Boolean, default=False)


class TaskRow(Base):
    __tablename__ = 'tasks'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(10))
    assignee: Mapped[str] = mapped_column(String(100))
    dueDate: Mapped[str] = mapped_column(String(10))
    archived: Mapped[bool] = mapped_column(Boolean)
    position: Mapped[int] = mapped_column(Integer, index=True)
    comments: Mapped[list['CommentRow']] = relationship(
        cascade='all, delete-orphan', order_by='CommentRow.position')


class CommentRow(Base):
    __tablename__ = 'comments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


def detached(row):
    return Task(**{key: getattr(row, key) for key in Task.model_fields if key != 'comments'},
                comments=[Comment(id=c.id, name=c.name, text=c.text) for c in row.comments])


class SQLAlchemyRepository:
    """One session/transaction per operation; a board row serializes writers.

    The database lock covers validation and ordering across repository instances.
    The local lock also protects the shared connection of in-memory SQLite tests.
    """
    def __init__(self, database_url, tasks=None):
        options = {}
        if database_url in ('sqlite://', 'sqlite:///:memory:'):
            options = {'poolclass': StaticPool, 'connect_args': {'check_same_thread': False}}
        self.engine = create_engine(database_url, **options)
        self._lock = RLock()
        Base.metadata.create_all(self.engine)
        from sqlalchemy.exc import IntegrityError
        try:
            with Session(self.engine) as session, session.begin():
                if session.get(BoardRow, 1) is None:
                    session.add(BoardRow(id=1, initialized=False))
        except IntegrityError:
            # Another process may have created the singleton concurrently.
            pass
        with self._session(write=True) as session:
            board = session.get(BoardRow, 1)
            if not board.initialized:
                for position, task in enumerate(tasks or []):
                    row = TaskRow(**task.model_dump(exclude={'comments'}), position=position)
                    row.comments = [CommentRow(**c.model_dump(), position=i)
                                    for i, c in enumerate(task.comments)]
                    session.add(row)
                board.initialized = True

    def close(self):
        self.engine.dispose()

    @contextmanager
    def _session(self, write=False):
        with self._lock, Session(self.engine) as session, session.begin():
            if write:
                session.execute(update(BoardRow).where(BoardRow.id == 1)
                                .values(initialized=BoardRow.initialized))
            yield session

    def _get(self, session, task_id):
        row = session.get(TaskRow, task_id)
        if row is None:
            raise NotFound('Task not found.')
        return row

    def list(self, archived=False, search='', assignee='', priority=''):
        with self._session() as session:
            query = select(TaskRow).where(TaskRow.archived == archived).order_by(TaskRow.position, TaskRow.id)
            if assignee:
                query = query.where(TaskRow.assignee == assignee)
            if priority:
                query = query.where(TaskRow.priority == priority)
            # Python matching preserves literal substring and Unicode behavior across dialects.
            return [detached(row) for row in session.scalars(query)
                    if search.strip().lower() in row.title.lower()]

    def create(self, fields):
        from sqlalchemy import func
        with self._session(write=True) as session:
            last = session.scalar(select(func.max(TaskRow.position)))
            row = TaskRow(id=str(uuid4()), **fields.model_dump(), archived=False,
                          position=0 if last is None else last + 1, comments=[])
            session.add(row)
            return detached(row)

    def update(self, task_id, fields):
        with self._session(write=True) as session:
            row = self._get(session, task_id)
            values = fields.model_dump(exclude_unset=True)
            if row.archived and values.get('status', row.status) != 'Done':
                raise Conflict('Archived tasks must remain Done.')
            for key, value in values.items():
                setattr(row, key, value)
            return detached(row)

    def remove(self, task_id):
        with self._session(write=True) as session:
            session.delete(self._get(session, task_id))
            return True

    def move(self, task_id, status, before_id=None):
        with self._session(write=True) as session:
            row = self._get(session, task_id)
            if row.archived:
                raise Conflict('Cannot move this task.')
            if before_id == task_id:
                return detached(row)
            before = self._get(session, before_id) if before_id is not None else None
            if before and (before.archived or before.status != status):
                raise Conflict('Invalid drop target.')
            rows = list(session.scalars(select(TaskRow).order_by(TaskRow.position, TaskRow.id)))
            rows.remove(row)
            rows.insert(rows.index(before) if before else len(rows), row)
            for position, item in enumerate(rows):
                item.position = position
            row.status = status
            return detached(row)

    def archive(self, task_id, archived=True):
        with self._session(write=True) as session:
            row = self._get(session, task_id)
            if row.status != 'Done':
                raise Conflict('Only completed tasks can be archived.')
            row.archived = archived
            return detached(row)

    def save_comment(self, task_id, fields, comment_id=None):
        with self._session(write=True) as session:
            row = self._get(session, task_id)
            if comment_id is None:
                row.comments.append(CommentRow(id=str(uuid4()), **fields.model_dump(),
                    position=max((c.position for c in row.comments), default=-1) + 1))
            else:
                comment = next((c for c in row.comments if c.id == comment_id), None)
                if comment is None:
                    raise NotFound('Comment not found.')
                comment.name, comment.text = fields.name, fields.text
            return detached(row)

    def delete_comment(self, task_id, comment_id):
        with self._session(write=True) as session:
            row = self._get(session, task_id)
            row.comments = [c for c in row.comments if c.id != comment_id]
            return detached(row)
