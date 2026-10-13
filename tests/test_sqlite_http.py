from hypothesis import settings

from src.sqlite_store import SqliteStore
from tests import test_http


class SqliteMachine(test_http.HttpMachine):
    store_class = SqliteStore
    suffix = ".sqlite"


TestSqliteHttp = SqliteMachine.TestCase
TestSqliteHttp.settings = settings(
    max_examples=5, stateful_step_count=10, deadline=None,
)
