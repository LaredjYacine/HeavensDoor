from celery import Celery

from ..services.credentials import redisurl

celery_app = Celery(
    "ai_agent",
    broker=redisurl,
    backend=redisurl,
    worker_pool="solo",
    include=["heavensdoor.app.routes.background_Process"],
)
