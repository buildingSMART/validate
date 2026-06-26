from redis import Redis
from redis.lock import Lock
import logging

from django.core.management.base import BaseCommand

from core.settings import CELERY_BROKER_URL

logger = logging.getLogger(__name__)
redis_client: Redis = Redis.from_url(CELERY_BROKER_URL, decode_responses=True)

class Command(BaseCommand):

    help = (
        'Scans and displays all current user locks (user ID, task name, TTL)'
    )

    def handle(self, *args, **options):
        
        # Scan for keys matching the lock pattern
        lock_pattern = "lock:celery:user:*:task:*"
        lock_keys = redis_client.keys(lock_pattern)

        if not lock_keys:
            logger.info("No active user locks found.")
            return

        logger.info(f"Found {len(lock_keys)} active user lock(s):")
        for key in lock_keys:
            # Extract user_id and task_name from the key
            parts = key.split(":")
            if len(parts) >= 6:
                user_id = parts[3]
                task_name = parts[5]
                ttl = redis_client.ttl(key)
                logger.info(f"- User ID: {user_id}, Task: {task_name}, TTL: {ttl:,} seconds")
