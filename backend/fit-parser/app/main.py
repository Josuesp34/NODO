from fastapi import FastAPI
from app.core.config import settings
from app.api.routes import router as fit_router

def get_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description="Microservicio de ingesta y modelado de datos biométricos",
        version="0.1.0"
    )

    # Registro de rutas (Endpoints)
    application.include_router(fit_router, prefix=settings.API_V1_STR)

    return application

app = get_application()

@app.get("/health", tags=["System"])
async def health_check():
    """Endpoint de salud para monitorización en Kubernetes/Cloud"""
    return {"status": "ok", "environment": settings.ENVIRONMENT}