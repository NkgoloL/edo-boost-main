# Integration Guide: Durable Audit Trail (Fourth Estate)

**Integration Status:** ✅ Complete (Implemented 2026-04-30)

This module migrates the EduBoost SA audit trail from volatile Redis Streams to a durable RabbitMQ architecture, ensuring POPIA compliance for immutable event logging.

## 1. Prerequisites
Add the following to your `requirements.txt`:
```text
aio-pika>=9.4.0
```

## 2. Environment Variables
Update your `.env` file or environment config:
```bash
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

## 3. Infrastructure (Docker)
If you don't have RabbitMQ running, add this to your `docker-compose.yml`:
```yaml
  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
```

## 4. Integration Steps
1.  **Replace Service**: Overwrite `app/services/fourth_estate.py` with the provided file.
2.  **App Lifecycle**: In your FastAPI `main.py`, add the connection logic to the startup and shutdown events:
    ```python
    from app.services.fourth_estate import fourth_estate

    @app.on_event("startup")
    async def startup():
        await fourth_estate.connect()

    @app.on_event("shutdown")
    async def shutdown():
        await fourth_estate.close()
    ```
3.  **Logging Events**: Use the service in your orchestrators (Executive/Judiciary):
    ```python
    from app.services.fourth_estate import fourth_estate, AuditEvent
    import uuid

    event = AuditEvent(
        event_id=str(uuid.uuid4()),
        action="PII_SCRUB_SUCCESS",
        learner_id_hash=hashed_id,
        actor_role="SYSTEM_JUDICIARY",
        metadata={"pillar": "Judiciary", "status": "validated"}
    )
    await fourth_estate.publish_event(event)
    ```

## 5. Verification
Log into the RabbitMQ Management UI (`http://localhost:15672`) to see the `eduboost_audit_log` exchange and verify that messages are marked as "Persistent".