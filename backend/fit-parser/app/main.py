from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import router
from app.api.auth_routes import router as auth_router
from app.api.planning_routes import router as planning_router
from app.core.config import settings
from app.core.database import get_db


def get_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description="Base de desarrollo: ingesta FIT para el futuro copiloto del entrenador",
        version="0.2.0",
    )
    application.include_router(router, prefix=settings.API_V1_STR)
    application.include_router(auth_router, prefix=settings.API_V1_STR)
    application.include_router(planning_router, prefix=settings.API_V1_STR)

    @application.get("/health", tags=["System"])
    async def health_check(db: AsyncSession = Depends(get_db)):
        """Readiness de solo lectura; nunca crea extensiones ni tablas."""
        try:
            result = await db.execute(text(
                "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'"
            ))
            if not result.scalar():
                raise HTTPException(status_code=503, detail="TimescaleDB no inicializada")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=503, detail="Base de datos no disponible") from None
        return {"status": "ok", "environment": settings.ENVIRONMENT}

    return application


app = get_application()
