from __future__ import annotations

import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from demo.settings import PROJECT_ROOT, settings


STATIC_DIR = PROJECT_ROOT / "demo" / "web" / "static"


async def index(_) -> FileResponse:
    """Serve the main index.html page."""
    return FileResponse(STATIC_DIR / "index.html")


# Create the web application
app = Starlette(
    routes=[
        Route("/", index),
        Mount("/static", StaticFiles(directory=STATIC_DIR), name="static"),
    ]
)


def main() -> None:
    """Run the web server."""
    uvicorn.run("demo.web.server:app", host=settings.web_host, port=settings.web_port, reload=False)


if __name__ == "__main__":
    main()
