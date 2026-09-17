# main.py
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .services.limiter import limiter
from .routes.Apiagent import route
import dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
dotenv.load_dotenv()
import os
app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)#type: ignore
app.include_router(route)
app.mount(
    "/static",
    StaticFiles(directory="src/heavensdoor/app/static"),
    name="static"
)

@app.get("/", response_class=HTMLResponse)
def index():
    with open("src/heavensdoor/app/static/Front.html", "r") as f:
        html = f.read()

    backend_url = os.getenv("backendurl")

    return html.replace(
        "__BACKEND_URL__",
        backend_url
    )
