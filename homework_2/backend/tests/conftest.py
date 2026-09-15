"""Run the contract against SQLite and any explicitly configured test servers.

External URLs must point to disposable test servers with CREATE DATABASE rights.
Each test gets a uniquely named database; existing databases are never modified.
"""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


@pytest.fixture(params=['sqlite', 'postgresql', 'mysql'])
def database_url(request, tmp_path):
    dialect = request.param
    if dialect == 'sqlite':
        yield 'sqlite:///' + (tmp_path / 'test.db').as_posix()
        return
    value = os.environ.get('TEST_' + dialect.upper() + '_URL')
    if not value:
        pytest.skip(f'TEST_{dialect.upper()}_URL is not configured')
    url = make_url(value)
    if url.get_backend_name() != dialect:
        pytest.fail(f'Test URL must use the {dialect} dialect')
    name = 'littleboard_test_' + uuid4().hex
    admin = create_engine(url, isolation_level='AUTOCOMMIT')
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE {name}')
        try:
            yield url.set(database=name).render_as_string(hide_password=False)
        finally:
            with admin.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE {name}')
    finally:
        admin.dispose()
