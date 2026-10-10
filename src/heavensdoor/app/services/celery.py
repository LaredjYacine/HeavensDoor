import os
import sys

from celery import Celery

from ..services.credentials import redisurl

POOL = "prefork"
if os.environ.get("CELERY_POOL"):
    POOL = os.environ["CELERY_POOL"]
elif sys.platform == "win32":
    POOL = "solo"
celery_app = Celery(
    "ai_agent",
    broker=redisurl,
    backend=redisurl,
    worker_pool=POOL,
    include=[
        "heavensdoor.app.routes.background_Process",
        "heavensdoor.app.routes.Stream_Process",
    ],
)
