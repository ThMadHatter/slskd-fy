import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import CacheEntry, CacheMetric
from app.services.cache_service import CacheService

engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_cache_set_and_get():
    db = TestingSessionLocal()

    CacheService.set(db, "test_key", {"data": "hello"}, "artist", ttl_seconds=10)

    # Assert entry in DB
    entry = db.query(CacheEntry).filter(CacheEntry.key == "test_key").first()
    assert entry is not None
    assert entry.entity_type == "artist"

    # Get from cache
    val = CacheService.get(db, "test_key", "artist")
    assert val == {"data": "hello"}

    # Metrics assert
    metrics = CacheService.get_metrics(db)
    assert metrics["artist"]["hits"] == 1
    assert metrics["artist"]["misses"] == 0

    db.close()

def test_cache_expiration():
    db = TestingSessionLocal()

    CacheService.set(db, "expired_key", {"data": "old"}, "artist", ttl_seconds=-10)

    val = CacheService.get(db, "expired_key", "artist")
    assert val is None

    metrics = CacheService.get_metrics(db)
    assert metrics["artist"]["hits"] == 0
    assert metrics["artist"]["misses"] == 1

    db.close()

def test_clear_expired():
    db = TestingSessionLocal()

    CacheService.set(db, "key1", "val1", "artist", ttl_seconds=-10)
    CacheService.set(db, "key2", "val2", "artist", ttl_seconds=10)

    deleted = CacheService.clear_expired(db)
    assert deleted == 1

    entry1 = db.query(CacheEntry).filter(CacheEntry.key == "key1").first()
    assert entry1 is None

    entry2 = db.query(CacheEntry).filter(CacheEntry.key == "key2").first()
    assert entry2 is not None

    db.close()
