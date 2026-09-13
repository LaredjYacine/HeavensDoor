# main.py
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .services.limiter import limiter

app = FastAPI()

# Attach to app.state so slowapi's global handlers know it exists
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)#type: ignore

# ... include your routers ...
