from celery import Celery

from ..services.credentials import redisurl

# POOL = "prefork"                 #:  THis is commented because it eats up all the ram from the render website
# if os.environ.get("CELERY_POOL"):
#     POOL = os.environ["CELERY_POOL"]
# elif sys.platform == "win32":
#     POOL = "solo"
celery_app = Celery(
    "ai_agent",
    broker=redisurl,
    backend=redisurl,
    worker_pool="solo",
    include=[
        "heavensdoor.app.routes.background_Process",
        "heavensdoor.app.routes.Stream_Process",
    ],
)
