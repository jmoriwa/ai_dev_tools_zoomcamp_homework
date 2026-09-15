from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate


@pytest.fixture
def client():
    from littleboard.main import create_app
    from littleboard.repository import MemoryRepository

    with TestClient(create_app(MemoryRepository())) as client:
        yield client


def create(client, **changes):
    response = client.post('/api/tasks', json={
        'title': '  New task  ', 'status': 'To Do', 'priority': 'High', **changes,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_crud_defaults_and_partial_update(client):
    task = create(client)
    assert task == dict(id=task['id'], title='New task', status='To Do', priority='High',
                        description='', assignee='', dueDate='', archived=False, comments=[])
    url = '/api/tasks/' + task['id']
    assert client.patch(url, json={}).json() == task
    updated = client.patch(url, json={'title': ' Edited ', 'description': 'Details',
                                     'dueDate': '2028-02-29', 'assignee': 'Sam Rivera'}).json()
    assert updated == {**task, 'title': 'Edited', 'description': 'Details',
                       'dueDate': '2028-02-29', 'assignee': 'Sam Rivera'}
    assert client.get('/api/tasks').json() == [updated]
    assert client.delete(url).json() is True
    assert client.get('/api/tasks').json() == []
    assert client.delete(url).status_code == 404


def test_filters(client):
    a = create(client, assignee='Alex Morgan')
    create(client, title='Another', priority='Low')
    done = create(client, status='Done')
    client.patch(f"/api/tasks/{done['id']}/archive", json={})
    assert client.get('/api/tasks', params={'search': ' NEW ', 'assignee': 'Alex Morgan',
                                          'priority': 'High'}).json() == [a]
    assert client.get('/api/tasks', params={'search': 'new', 'priority': 'Low'}).json() == []
    assert len(client.get('/api/tasks', params={'assignee': '', 'priority': ''}).json()) == 2
    assert [t['id'] for t in client.get('/api/tasks?archived=true').json()] == [done['id']]


def test_movement_and_update_order(client):
    a, b, c = [create(client, title=name) for name in ['A', 'B', 'C']]
    def move(task, **body):
        return client.post(f"/api/tasks/{task['id']}/move", json=body)
    def ids():
        return [t['id'] for t in client.get('/api/tasks').json()]
    assert move(c, status='To Do', beforeId=a['id']).status_code == 200
    assert ids() == [c['id'], a['id'], b['id']]
    move(c, status='Backlog', beforeId=None)
    assert ids() == [a['id'], b['id'], c['id']]
    assert move(a, status='Done', beforeId=a['id']).json() == a
    client.patch(f"/api/tasks/{a['id']}", json={'status': 'Backlog'})
    assert ids() == [a['id'], b['id'], c['id']]
    move(c, status='Backlog', beforeId=a['id'])
    assert ids() == [c['id'], a['id'], b['id']]


def test_archive_comments_and_restore(client):
    task = create(client, status='Done')
    url = f"/api/tasks/{task['id']}"
    assert client.patch(url + '/archive', json={}).json()['archived'] is True
    added = client.post(url + '/comments', json={'name': 'Jamie Chen', 'text': ' First '})
    assert added.status_code == 201
    comment = added.json()['comments'][0]
    assert comment['text'] == 'First'
    client.post(url + '/comments', json={'name': 'Sam Rivera', 'text': 'Second'})
    edited = client.put(url + '/comments/' + comment['id'],
                        json={'name': 'Alex Morgan', 'text': ' Edited '})
    assert edited.status_code == 200
    assert edited.json()['comments'][0] == {**comment, 'name': 'Alex Morgan', 'text': 'Edited'}
    assert len(edited.json()['comments']) == 2
    assert client.patch(url + '/archive', json={}).json() == edited.json()
    restored = client.patch(url + '/archive', json={'archived': False}).json()
    assert restored == {**edited.json(), 'archived': False}
    assert client.get('/api/tasks').json() == [restored]
    deleted = client.delete(url + '/comments/' + comment['id']).json()
    assert len(deleted['comments']) == 1
    assert client.delete(url + '/comments/missing').json() == deleted
    client.patch(url + '/archive', json={})
    assert client.delete(url).json() is True
    assert client.get('/api/tasks?archived=true').json() == []


@pytest.mark.parametrize('changes', [
    {'title': ' \t'}, {'title': None}, {'title': 3}, {'status': 'Unknown'},
    {'priority': 'Urgent'}, {'assignee': 'Unknown'}, {'dueDate': '2026-02-30'},
    {'dueDate': '2026-2-03'}, {'dueDate': None}, {'description': None},
    {'archived': True}, {'comments': []}, {'id': 'injected'},
])
def test_invalid_task_writes_are_atomic(client, changes):
    task = create(client)
    assert client.post('/api/tasks', json={
        'title': 'Valid', 'status': 'Done', 'priority': 'Low', **changes,
    }).status_code == 422
    response = client.patch('/api/tasks/' + task['id'], json=changes)
    assert response.status_code == 422
    assert isinstance(response.json()['detail'], list)
    assert client.get('/api/tasks').json() == [task]


@pytest.mark.parametrize('query', ['archived=maybe', 'assignee=Nobody', 'priority=Urgent'])
def test_invalid_filters(client, query):
    assert client.get('/api/tasks?' + query).status_code == 422


def test_conflicts_and_missing_targets_leave_data_unchanged(client):
    a = create(client)
    b = create(client, status='Done')
    archived = client.patch(f"/api/tasks/{b['id']}/archive", json={}).json()
    url = f"/api/tasks/{a['id']}"
    for value in [True, False]:
        assert client.patch(url + '/archive', json={'archived': value}).status_code == 409
    for target, status, expected in [(b['id'], 'Done', 409), ('absent', 'Done', 404),
                                     (a['id'], 'Unknown', 422)]:
        assert client.post(url + '/move', json={'status': status, 'beforeId': target}).status_code == expected
    archived_url = f"/api/tasks/{b['id']}"
    assert client.post(archived_url + '/move', json={'status': 'Done', 'beforeId': b['id']}).status_code == 409
    assert client.patch(archived_url, json={'status': 'Backlog', 'title': 'Changed'}).status_code == 409
    c = create(client, status='Backlog')
    assert client.post(url + '/move', json={'status': 'Done', 'beforeId': c['id']}).status_code == 409
    assert client.get('/api/tasks').json() == [a, c]
    assert client.get('/api/tasks?archived=true').json() == [archived]


@pytest.mark.parametrize('method,suffix,body', [
    ('patch', '', {}), ('delete', '', None), ('post', '/move', {'status': 'Done'}),
    ('patch', '/archive', {}), ('post', '/comments', {'name': 'Sam Rivera', 'text': 'Hi'}),
    ('put', '/comments/missing', {'name': 'Sam Rivera', 'text': 'Hi'}),
    ('delete', '/comments/missing', None),
])
def test_missing_tasks(client, method, suffix, body):
    response = client.request(method, '/api/tasks/missing' + suffix, **({'json': body} if body is not None else {}))
    assert response.status_code == 404
    assert isinstance(response.json()['detail'], str)


def test_invalid_comments_and_bodies(client):
    task = create(client)
    url = f"/api/tasks/{task['id']}"
    for body in [{'name': 'Sam Rivera', 'text': ' '}, {'name': 'Nobody', 'text': 'Hi'},
                 {'text': 'Hi'}, {'name': 'Sam Rivera', 'text': None},
                 {'name': 'Sam Rivera', 'text': 'Hi', 'id': 'injected'}]:
        assert client.post(url + '/comments', json=body).status_code == 422
        assert client.put(url + '/comments/missing', json=body).status_code == 422
    assert client.put(url + '/comments/missing', json={'name': 'Sam Rivera', 'text': 'Hi'}).status_code == 404
    for path, method, body in [('/api/tasks', 'post', {}), (url + '/move', 'post', {}),
                               (url + '/move', 'post', {'status': 'Done', 'beforeId': ''}),
                               (url + '/archive', 'patch', {'archived': 'true'}),
                               (url, 'patch', None)]:
        assert client.request(method, path, json=body).status_code == 422
    assert client.get('/api/tasks').json() == [task]


def test_contract_and_runtime_routes(client):
    spec = yaml.safe_load((Path(__file__).parents[2] / 'openapi.yaml').read_text())
    validate(spec)
    runtime = client.get('/openapi.json').json()
    for path, operations in spec['paths'].items():
        for method in operations.keys() & {'get', 'post', 'put', 'patch', 'delete'}:
            assert runtime['paths']['/api' + path][method]['operationId'] == operations[method]['operationId']
    schema = {'$ref': '#/components/schemas/Task', 'components': spec['components']}
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(create(client))


def test_default_app_has_independent_demo_data():
    from littleboard.main import create_app
    with TestClient(create_app()) as first, TestClient(create_app()) as second:
        active = first.get('/api/tasks').json()
        assert {t['status'] for t in active} == {'Backlog', 'To Do', 'In Progress', 'Done'}
        assert any(t['comments'] for t in active)
        assert first.get('/api/tasks?archived=true').json()
        first.delete('/api/tasks/' + active[0]['id'])
        assert second.get('/api/tasks').json() == active
