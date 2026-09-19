from   celery import   Celery
import dotenv
import os
from ..services.credentials import redisurl
celery_app = Celery('ai_agent', broker=redisurl, backend=redisurl,worker_pool="solo",  include=['heavensdoor.app.routes.background_Process'])
