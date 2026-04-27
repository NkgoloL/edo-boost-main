import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.api.fourth_estate import FourthEstate
from app.api.constitutional_schema.types import AuditEvent, EventType
from datetime import datetime, timedelta, timezone

@pytest.mark.asyncio
async def test_fourth_estate_circuit_breaker_flow():
    # Setup FourthEstate with a low threshold for testing
    fe = FourthEstate(redis_url="redis://localhost:6379", cb_threshold=2, cb_recovery_timeout=1)
    
    event = AuditEvent(
        event_type=EventType.LLM_CALL_COMPLETED,
        pillar="EXECUTIVE",
        payload={"test": "data"}
    )

    # 1. Test CLOSED state (successful publish)
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.xadd = AsyncMock(return_value="12345-0")
        mock_from_url.return_value = mock_redis
        
        await fe.publish(event)
        assert fe._cb_state == "CLOSED"
        assert mock_redis.xadd.called

    fe._redis = None
    # 2. Test transition to OPEN state (2 failures as per threshold)
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.xadd = AsyncMock(side_effect=Exception("Redis Down"))
        mock_from_url.return_value = mock_redis
        
        # Failure 1
        await fe.publish(event)
        assert fe._cb_state == "CLOSED"
        assert fe._cb_failure_count == 1
        
        # Failure 2 -> Should trigger OPEN
        await fe.publish(event)
        assert fe._cb_state == "OPEN"
        assert fe._cb_failure_count == 2

    # 3. Test skipping Redis while OPEN
    with patch("app.api.fourth_estate.logger") as mock_logger:
        await fe.publish(event)
        mock_logger.warning.assert_called_with("circuit_breaker_open_skipping_redis", event_id=event.event_id)
        assert fe._cb_state == "OPEN"

    # 4. Test transition to HALF_OPEN (after recovery timeout)
    # Fast-forward time by manually adjusting last_failure_time
    fe._cb_last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=2)
    fe._redis = None
    
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.xadd = AsyncMock(return_value="12345-1")
        mock_from_url.return_value = mock_redis
        
        await fe.publish(event)
        assert fe._cb_state == "CLOSED" # HALF_OPEN -> SUCCESS -> CLOSED
        assert fe._cb_failure_count == 0
        assert mock_redis.xadd.called

@pytest.mark.asyncio
async def test_fourth_estate_circuit_breaker_reopen():
    fe = FourthEstate(redis_url="redis://localhost:6379", cb_threshold=1, cb_recovery_timeout=0)
    fe._cb_state = "OPEN"
    fe._cb_last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=1)
    
    event = AuditEvent(
        event_type=EventType.LLM_CALL_COMPLETED,
        pillar="EXECUTIVE",
        payload={"test": "data"}
    )

    # HALF_OPEN -> FAILURE -> OPEN
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.xadd = AsyncMock(side_effect=Exception("Still Down"))
        mock_from_url.return_value = mock_redis
        
        await fe.publish(event)
        assert fe._cb_state == "OPEN"
        assert fe._cb_failure_count > 0
