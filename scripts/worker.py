
import asyncio
import json
import logging
import os
import sys

# Add current directory to python path to find 'app'
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.api.endpoints.telemetry import telemetry_points_total
from app.services.kafka_service import KafkaService
from app.services.iot_service import IoTService
from app.schemas.telemetry import SensorReadingCreate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("iot-worker")

async def process_message(db, message: dict):
    """Process a single message and save to DB."""
    try:
        # Validate and convert to schema
        reading_data = SensorReadingCreate(**message)
        
        # synchronous db write
        IoTService.create_reading(db, reading_data)
        
        logger.info(f"Ingested reading for device {reading_data.device_id}")
    except Exception as e:
        logger.error(f"Error processing message: {e}")

async def main():
    logger.info("Starting IoT Worker...")
    
    kafka_service = KafkaService()
    db = SessionLocal()
    
    try:
        # Get consumer for "iot_stream_v1"
        consumer = await kafka_service._get_consumer("iot_stream_v1")
        if not consumer:
            logger.error("Failed to connect to Kafka. Exiting.")
            return

        logger.info("Connected to Kafka. Listening for messages...")
        
        async for msg in consumer:
            try:
                value = json.loads(msg.value.decode("utf-8"))
                await process_message(db, value)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode message: {msg.value}")
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}")
                
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
    finally:
        db.close()
        await kafka_service.close()
        logger.info("Worker stopped.")

if __name__ == "__main__":
    asyncio.run(main())
