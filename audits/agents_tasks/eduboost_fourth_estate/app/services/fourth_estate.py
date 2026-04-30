import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import aio_pika
from pydantic import BaseModel, Field
from app.core.config import settings

logger = logging.getLogger(__name__)

class AuditEvent(BaseModel):
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str
    pillar: str = "Fourth Estate"
    learner_id_hash: str
    actor_role: str
    metadata: Dict[str, Any] = {}

class FourthEstateService:
    """
    Durable Audit Trail Service (Pillar 4).
    Migrated from Redis Streams to RabbitMQ for POPIA-grade persistence.
    """
    def __init__(self):
        self.url = settings.RABBITMQ_URL
        self.exchange_name = "eduboost_audit_log"
        self._connection = None
        self._channel = None

    async def connect(self):
        if not self._connection or self._connection.is_closed:
            self._connection = await aio_pika.connect_robust(self.url)
            self._channel = await self._connection.channel()
            # Declare a fanout exchange for durability and broadcasting
            self.exchange = await self._channel.declare_exchange(
                self.exchange_name, 
                aio_pika.ExchangeType.FANOUT, 
                durable=True
            )
            logger.info(f"Connected to Fourth Estate Durable Bus (RabbitMQ) at {self.url}")

    async def publish_event(self, event: AuditEvent):
        """Publishes an immutable audit event to the durable broker."""
        if not self._channel:
            await self.connect()
            
        message_body = event.model_dump_json().encode()
        message = aio_pika.Message(
            body=message_body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT, # Ensure persistence on disk
            content_type="application/json",
            timestamp=int(event.timestamp.timestamp())
        )
        
        await self.exchange.publish(message, routing_key="")
        logger.info(f"Audit Logged: {event.action} | {event.event_id}")

    async def close(self):
        if self._connection:
            await self._connection.close()

# Global instance for dependency injection
fourth_estate = FourthEstateService()