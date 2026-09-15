from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Path, Request
from fastapi.responses import JSONResponse

from .models import ArchiveInput, CommentInput, Error, MoveInput, OptionalAssignee, PriorityFilter, Task, TaskCreate, TaskUpdate
from .repository import Conflict, MemoryRepository, NotFound, TaskRepository
from .seed import demo_tasks


def get_repository(request: Request) -> TaskRepository:
    return request.app.state.repository


Repository = Annotated[TaskRepository, Depends(get_repository)]
Id = Annotated[str, Path(min_length=1)]
router = APIRouter(prefix='/api')


@router.get('/tasks', response_model=list[Task], operation_id='listTasks', tags=['Tasks'])
def list_tasks(repository: Repository, archived: bool = False, search: str = '',
               assignee: OptionalAssignee = '', priority: PriorityFilter = ''):
    return repository.list(archived, search, assignee, priority)


@router.post('/tasks', response_model=Task, status_code=201, operation_id='createTask', tags=['Tasks'])
def create_task(fields: TaskCreate, repository: Repository):
    return repository.create(fields)


@router.patch('/tasks/{taskId}', response_model=Task, operation_id='updateTask', tags=['Tasks'])
def update_task(taskId: Id, fields: TaskUpdate, repository: Repository):
    return repository.update(taskId, fields)


@router.delete('/tasks/{taskId}', response_model=Literal[True], operation_id='deleteTask', tags=['Tasks'])
def delete_task(taskId: Id, repository: Repository):
    return repository.remove(taskId)


@router.post('/tasks/{taskId}/move', response_model=Task, operation_id='moveTask', tags=['Tasks'])
def move_task(taskId: Id, fields: MoveInput, repository: Repository):
    return repository.move(taskId, fields.status, fields.beforeId)


@router.patch('/tasks/{taskId}/archive', response_model=Task, operation_id='archiveTask', tags=['Tasks'])
def archive_task(taskId: Id, fields: ArchiveInput, repository: Repository):
    return repository.archive(taskId, fields.archived)


@router.post('/tasks/{taskId}/comments', response_model=Task, status_code=201,
             operation_id='createComment', tags=['Comments'])
def create_comment(taskId: Id, fields: CommentInput, repository: Repository):
    return repository.save_comment(taskId, fields)


@router.put('/tasks/{taskId}/comments/{commentId}', response_model=Task,
            operation_id='updateComment', tags=['Comments'])
def update_comment(taskId: Id, commentId: Id, fields: CommentInput, repository: Repository):
    return repository.save_comment(taskId, fields, commentId)


@router.delete('/tasks/{taskId}/comments/{commentId}', response_model=Task,
               operation_id='deleteComment', tags=['Comments'])
def delete_comment(taskId: Id, commentId: Id, repository: Repository):
    return repository.delete_comment(taskId, commentId)


def create_app(repository: TaskRepository | None = None) -> FastAPI:
    app = FastAPI(title='Littleboard API', version='1.0.0')
    app.state.repository = repository if repository is not None else MemoryRepository(demo_tasks())

    @app.exception_handler(NotFound)
    async def not_found(request: Request, exc: NotFound):
        return JSONResponse(status_code=404, content={'detail': str(exc)})

    @app.exception_handler(Conflict)
    async def conflict(request: Request, exc: Conflict):
        return JSONResponse(status_code=409, content={'detail': str(exc)})

    # Describe domain errors only on routes that can produce them.
    for route in router.routes:
        if '{taskId}' in route.path:
            route.responses[404] = {'model': Error, 'description': 'Resource not found'}
        if route.operation_id in {'updateTask', 'moveTask', 'archiveTask'}:
            route.responses[409] = {'model': Error, 'description': 'Task state conflict'}
    app.include_router(router)
    return app


app = create_app()
