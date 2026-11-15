import os
from pathlib import Path

# main.py
import dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .routes.api_agent import route
from .routes.authentification import auth
from .routes.streaming_api import stream_router
from .services.limiter import limiter

dotenv.load_dotenv()

app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
app.include_router(route)
app.include_router(stream_router)
app.include_router(auth)
app.mount("/static", StaticFiles(directory="src/heavensdoor/app/static"), name="static")

STATIC_DIR = Path("src/heavensdoor/app/static")


@app.get("/auth/login", response_class=HTMLResponse)
def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/auth/signup", response_class=HTMLResponse)
def signup_page():
    return FileResponse(STATIC_DIR / "signup.html")


@app.get("/auth/confirm", response_class=HTMLResponse)
def confirm_page():
    return FileResponse(STATIC_DIR / "confirm.html")


@app.get("/apply-candidate", response_class=HTMLResponse)
def apply_candidate_page():
    return FileResponse(STATIC_DIR / "apply-candidate.html")


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
