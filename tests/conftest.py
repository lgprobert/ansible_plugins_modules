import tempfile
from pathlib import Path

import pytest
import yaml
from sqlalchemy.orm import sessionmaker
from sqlite import InventoryModule, initialize_database  # type: ignore # noqa


@pytest.fixture(scope="function")
def db_path():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name
    yield db_path
    Path(db_path).unlink()


@pytest.fixture(scope="function")
def db_engine(db_path):
    """Initialize the database and return the SQLAlchemy engine."""
    engine = initialize_database(db_path)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a new database session for each test."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="function")
def inventory_plugin():
    """Fixture to provide an instance of the InventoryModule."""
    plugin = InventoryModule()
    yield plugin


@pytest.fixture(scope="function")
def inventory_file(db_path, tmp_path):
    """Create a temporary inventory YAML file for testing."""
    inventory_data = {
        "plugin": "sqlite",
        "db_path": db_path,
    }
    inventory_file = tmp_path / "inventory.yml"
    with open(inventory_file, "w") as f:
        yaml.safe_dump(inventory_data, f)
    yield inventory_file
