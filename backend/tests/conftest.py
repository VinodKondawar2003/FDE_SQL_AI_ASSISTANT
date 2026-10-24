import pytest
from backend.app.sql.catalog import Catalog
from backend.app.sql.service import SqlService
from data.seed import seed


@pytest.fixture
def sql(tmp_path):
    path = tmp_path / "sample.db"
    seed(path)
    return SqlService(Catalog(path))
