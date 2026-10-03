from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.health import router as health_router
from app.api.patient import router as patient_router


def create_application() -> FastAPI:
    """Initialize and configure the FastAPI application."""
    application = FastAPI(
        title=settings.APP_NAME,
        description=(
            "MedChronicle is an AI-powered doctor/care-team-facing assistive tool for "
            "consultation preparation in the Cancer Care domain."
        ),
        version="0.1.0",
        debug=settings.DEBUG,
    )

    # Register API routers
    application.include_router(health_router)
    application.include_router(patient_router)

    # Mount static assets and doctor UI
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.is_dir():
        application.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

        @application.get("/", include_in_schema=False)
        @application.get("/ui", include_in_schema=False)
        def serve_ui():
            return FileResponse(frontend_dir / "index.html")

    return application


app = create_application()
