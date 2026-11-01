"""Celery application instance."""

from celery import Celery

from borsel.core.config import settings

celery_app = Celery(
    "borsel",
    broker=settings.REDIS_URL,
)

# Autodiscover task modules inside the borsel package.
celery_app.autodiscover_tasks(["borsel.tasks"])
