"""Test configuration and fixtures."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.rate_limit import init_rate_limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.iot import SensorReading
from app.schemas.telemetry import SensorReadingCreate

pytest_plugins = ("pytest_asyncio",)

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function", autouse=True)
def initialize_rate_limiter(event_loop):
    """Initialize rate limiter for all tests."""
    redis_url = "redis://localhost:6379/0"
    try:
        # Use a shorter timeout for tests
        event_loop.run_until_complete(
            asyncio.wait_for(init_rate_limiter(redis_url), timeout=5.0)
        )
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass


@pytest.fixture(scope="function", autouse=True)
def ensure_rate_limiter_initialized():
    """Ensure rate limiter is initialized for each test function."""
    try:
        from app.core.rate_limit import get_rate_limiter

        result = get_rate_limiter()
        if result is None:
            # If not initialized, try to initialize it with timeout
            import asyncio
            from app.core.rate_limit import init_rate_limiter
            redis_url = "redis://localhost:6379/0"
            try:
                asyncio.run(asyncio.wait_for(init_rate_limiter(redis_url), timeout=2.0))
            except Exception:
                pass
    except Exception:
        pass


class DummyIoTService:
    """Dummy IoT service for integration tests."""

    @staticmethod
    def create_reading(db, reading: SensorReadingCreate):
        """Create dummy sensor reading."""
        # Simulate validation error
        if not reading.device_id or reading.reading_value < -100:
            raise ValueError("Invalid reading input")

        # Create the object
        db_obj = SensorReading(
            id=1,
            device_id=str(reading.device_id),
            reading_value=reading.reading_value,
            reading_type=str(reading.reading_type),
            unit=str(reading.unit),
            battery_level=reading.battery_level,
            raw_data=str(reading.raw_data) if reading.raw_data else None,
            timestamp=datetime.now(timezone.utc),
        )

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def update_reading(db, reading_id: int, reading_data):
        """Update dummy reading."""
        db_obj = db.query(SensorReading).filter(SensorReading.id == reading_id).first()
        if not db_obj:
            return None

        if reading_data.reading_value is not None:
            db_obj.reading_value = reading_data.reading_value
        
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def get_readings(db, skip: int = 0, limit: int = 100):
        """Get dummy readings."""
        return [
            SensorReading(
                id=1,
                device_id="sensor-001",
                reading_value=25.0,
                reading_type="temp",
                unit="C",
                timestamp=datetime.now(timezone.utc),
            )
        ]

    @staticmethod
    def get_latest_reading_static(db, device_id: str, unit=None):
        """Get dummy latest reading."""
        return SensorReading(
            id=1,
            device_id=device_id,
            reading_value=25.0,
            reading_type="temp",
            unit="C",
            timestamp=datetime.now(timezone.utc),
        )

    @staticmethod
    def get_reading_by_id(db, reading_id: int):
        """Return None for unknown IDs to simulate 404."""
        if reading_id == 1:
            return SensorReading(
                id=1,
                device_id="sensor-001",
                reading_value=25.0,
                reading_type="temp",
                unit="C",
                timestamp=datetime.now(timezone.utc),
            )
        return None

    @staticmethod
    def get_all_devices(db):
        """Get all devices."""
        return ["sensor-001", "sensor-002"]


class DummyRedisService:
    """Dummy Redis service for integration tests."""

    async def get_latest_price(self, symbol: str):
        # Mapped to reading
        return {
            "device_id": symbol,
            "reading_value": 25.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database session."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def mock_redis_service():
    """Mock Redis service for testing."""
    mock_service = AsyncMock()
    mock_service.get_latest_price.return_value = {
        "device_id": "sensor-001",
        "reading_value": 25.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return mock_service
