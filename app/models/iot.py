"""IoT data models for the IoT Stream Engine."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import CHAR, TypeDecorator

from app.db.base import Base


# Cross-database UUID type
class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise stores as CHAR(36).
    """

    impl = CHAR

    def load_dialect_impl(self, dialect):
        """Return the appropriate type descriptor for the dialect."""
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        """Convert Python value to a value suitable for the database."""
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(value))
        return str(value)

    def process_result_value(self, value, dialect):
        """Convert database value to a Python UUID object."""
        if value is None:
            return value
        return uuid.UUID(value)


class TimestampMixin:
    """Timestamp mixin for models."""

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class SensorReading(Base):
    """Sensor reading model for storing IoT data."""

    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String, index=True, nullable=False)
    reading_value = Column(Float, nullable=False)
    reading_type = Column(String, nullable=False, index=True)
    unit = Column(String, nullable=False)
    battery_level = Column(Float, nullable=True)
    raw_data = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        """
        Return a string representation of the sensor reading.

        Returns:
            String representation of the sensor reading
        """
        return (
            f"<SensorReading(device_id='{self.device_id}', "
            f"type='{self.reading_type}', value={self.reading_value}, "
            f"timestamp='{self.timestamp}')>"
        )


class RawTelemetry(Base):
    """Raw telemetry model for storing unprocessed sensor data."""

    __tablename__ = "raw_telemetry"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String, index=True, nullable=False)
    raw_data = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    source = Column(String, nullable=False)  # Gateway or protocol source
    processed = Column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        """
        Return a string representation of the raw telemetry record.

        Returns:
            String representation of the raw telemetry record
        """
        return (
            f"<RawTelemetry(device_id='{self.device_id}', "
            f"timestamp='{self.timestamp}', processed={self.processed})>"
        )


class ProcessedReading(Base):
    """Processed reading model."""

    __tablename__ = "processed_readings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String, index=True, nullable=False)
    reading_value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_telemetry_id = Column(Integer, ForeignKey("raw_telemetry.id"))
    raw_telemetry = relationship("RawTelemetry")

    def __repr__(self) -> str:
        """
        Return a string representation of the processed reading.

        Returns:
            String representation of the processed reading
        """
        return (
            f"<ProcessedReading(device_id='{self.device_id}', "
            f"value={self.reading_value}, timestamp='{self.timestamp}')>"
        )


class RollingAverage(Base, TimestampMixin):
    """Model for storing rolling average calculations."""

    __tablename__ = "rolling_averages"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    device_id = Column(String, nullable=False, index=True)
    average_value = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    window_size = Column(Integer, nullable=False)
    reading_type = Column(String, nullable=False, default="default")


class PollingConfig(Base, TimestampMixin):
    """Polling config model."""

    __tablename__ = "polling_configs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id = Column(String, nullable=False, unique=True, index=True)
    device_ids = Column(JSON, nullable=False)  # Array of device IDs
    interval = Column(Integer, nullable=False)  # Interval in seconds
    status = Column(String, nullable=False)  # active, paused, completed
