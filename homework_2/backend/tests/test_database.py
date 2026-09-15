from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from littleboard.database import CommentRow, SQLAlchemyRepository, TaskRow
from littleboard.main import create_app
from littleboard.models import CommentInput, TaskCreate


def test_restart_persists_changes_and_does_not_reseed(database_url, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', database_url)
    with TestClient(create_app()) as client:
        tasks = client.get('/api/tasks').json()
        a, b = tasks[:2]
        client.patch('/api/tasks/' + a['id'], json={'title': 'Persistent edit'})
        client.post('/api/tasks/' + b['id'] + '/move', json={'status': a['status'], 'beforeId': a['id']})
        client.post('/api/tasks/' + a['id'] + '/comments', json={'name': 'Sam Rivera', 'text': 'Saved'})
        expected = client.get('/api/tasks').json()
        archived = client.get('/api/tasks?archived=true').json()
    with TestClient(create_app()) as client:
        assert client.get('/api/tasks').json() == expected
        assert client.get('/api/tasks?archived=true').json() == archived
        for task in expected + archived:
            assert client.delete('/api/tasks/' + task['id']).status_code == 200
    with TestClient(create_app()) as client:
        assert client.get('/api/tasks').json() == []
        assert client.get('/api/tasks?archived=true').json() == []


def test_rollback_detached_results_and_comment_cleanup(database_url):
    repo = SQLAlchemyRepository(database_url)
    try:
        task = repo.create(TaskCreate(title='Original', status='Done', priority='Low'))
        saved = repo.save_comment(task.id, CommentInput(name='Sam Rivera', text='Hello'))
        saved.title = 'External mutation'
        saved.comments.clear()
        assert repo.list()[0].title == 'Original'
        assert len(repo.list()[0].comments) == 1
        with pytest.raises(RuntimeError):
            with repo._session(write=True) as session:
                session.get(TaskRow, task.id).title = 'Rolled back'
                session.flush()
                raise RuntimeError('Failure after SQL write')
        assert repo.list()[0].title == 'Original'
        repo.remove(task.id)
        with repo._session() as session:
            assert session.scalar(select(func.count()).select_from(CommentRow)) == 0
    finally:
        repo.close()


def test_shared_database_concurrent_writes_and_literal_search(database_url):
    url = database_url
    first, second = SQLAlchemyRepository(url), SQLAlchemyRepository(url)
    try:
        def create(i):
            return (first if i % 2 else second).create(
                TaskCreate(title=f'Task {i}', status='To Do', priority='Low'))
        with ThreadPoolExecutor(max_workers=4) as pool:
            tasks = list(pool.map(create, range(20)))
        assert len(first.list()) == len(second.list()) == 20
        with first._session() as session:
            positions = list(session.scalars(select(TaskRow.position)))
            assert len(set(positions)) == 20
        special = first.create(TaskCreate(title='100%_ CAFÉ', status='Done', priority='High'))
        assert second.list(search='%_ café') == [special]
        def comment(i):
            return (first if i % 2 else second).save_comment(tasks[0].id,
                CommentInput(name='Sam Rivera', text=str(i)))
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(comment, range(12)))
        assert len(next(t for t in first.list() if t.id == tasks[0].id).comments) == 12
    finally:
        first.close()
        second.close()
