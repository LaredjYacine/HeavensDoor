# main.py
import dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .routes.Apiagent import route
from .services.limiter import limiter

dotenv.load_dotenv()
import os

app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
app.include_router(route)
app.mount("/static", StaticFiles(directory="src/heavensdoor/app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    with open("src/heavensdoor/app/static/Front.html", "r") as f:
        html = f.read()

    backend_url = os.getenv("backendurl")

    return html.replace("__BACKEND_URL__", backend_url)


@app.get("/about", response_class=HTMLResponse)
def about():
    with open("src/heavensdoor/app/static/About.html", "r") as f:
        return f.read()
