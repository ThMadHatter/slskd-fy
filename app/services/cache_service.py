import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Dict
from sqlalchemy.orm import Session
from app.models import CacheEntry, CacheMetric

logger = logging.getLogger("track_portal.cache_service")

class CacheService:
    @staticmethod
    def get(db: Session, key: str, entity_type: str) -> Optional[Any]:
        """
        Retrieves a cached value for the given key.
        Checks for expiration. Automatically records hit/miss metrics.
        """
        now = datetime.utcnow()
        entry = db.query(CacheEntry).filter(CacheEntry.key == key).first()

        # Fetch or create metric counter
        metric = db.query(CacheMetric).filter(CacheMetric.entity_type == entity_type).first()
        if not metric:
            metric = CacheMetric(entity_type=entity_type, hits=0, misses=0)
            db.add(metric)
            db.commit()
            # Re-fetch to bind to current session
            metric = db.query(CacheMetric).filter(CacheMetric.entity_type == entity_type).first()

        if entry:
            if entry.expires_at > now:
                # Cache Hit!
                metric.hits += 1
                db.commit()
                try:
                    return json.loads(entry.value)
                except Exception as e:
                    logger.error(f"Failed to parse cached JSON for key '{key}': {e}")
                    return None
            else:
                # Expired - Cache Miss!
                logger.info(f"Cache key '{key}' has expired.")
                db.delete(entry)
                db.commit()

        # Cache Miss!
        metric.misses += 1
        db.commit()
        return None

    @staticmethod
    def set(db: Session, key: str, value: Any, entity_type: str, ttl_seconds: int = 86400) -> None:
        """
        Sets a cache entry with the given TTL.
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds)
        serialized = json.dumps(value)

        # Check if key already exists
        entry = db.query(CacheEntry).filter(CacheEntry.key == key).first()
        if entry:
            entry.value = serialized
            entry.expires_at = expires_at
            entry.entity_type = entity_type
        else:
            entry = CacheEntry(
                key=key,
                value=serialized,
                entity_type=entity_type,
                expires_at=expires_at
            )
            db.add(entry)

        db.commit()
        logger.info(f"Cached key '{key}' under entity '{entity_type}' (TTL: {ttl_seconds}s)")

    @staticmethod
    def get_metrics(db: Session) -> Dict[str, Dict[str, int]]:
        """
        Returns hit and miss counts per entity_type.
        """
        metrics = db.query(CacheMetric).all()
        result = {}
        for m in metrics:
            result[m.entity_type] = {
                "hits": m.hits,
                "misses": m.misses
            }
        return result

    @staticmethod
    def clear_expired(db: Session) -> int:
        """
        Background/maintenance refresh: deletes all expired cache entries.
        """
        now = datetime.utcnow()
        deleted = db.query(CacheEntry).filter(CacheEntry.expires_at <= now).delete()
        db.commit()
        if deleted > 0:
            logger.info(f"Cleared {deleted} expired cache entries.")
        return deleted
