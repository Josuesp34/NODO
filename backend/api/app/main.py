from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.activity_routes import router as activity_router
from app.api.assistant_routes import router as assistant_router
from app.api.auth_routes import router as auth_router
from app.api.file_routes import router as file_router
from app.api.intervals_routes import router as intervals_router
from app.api.operations_routes import router as operations_router
from app.api.planning_routes import router as planning_router
from app.api.privacy_routes import router as privacy_router
from app.api.product_routes import router as product_router
from app.api.routes import router
from app.core.config import settings
from app.core.database import get_db


def get_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description="Backend de NODO para entrenador y atleta",
        version="0.5.0",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router, prefix=settings.API_V1_STR)
    application.include_router(auth_router, prefix=settings.API_V1_STR)
    application.include_router(planning_router, prefix=settings.API_V1_STR)
    application.include_router(activity_router, prefix=settings.API_V1_STR)
    application.include_router(file_router, prefix=settings.API_V1_STR)
    application.include_router(intervals_router, prefix=settings.API_V1_STR)
    application.include_router(operations_router, prefix=settings.API_V1_STR)
    application.include_router(privacy_router, prefix=settings.API_V1_STR)
    application.include_router(product_router, prefix=settings.API_V1_STR)
    application.include_router(assistant_router, prefix=settings.API_V1_STR)

    @application.get("/health", tags=["System"])
    async def health_check(db: AsyncSession = Depends(get_db)):
        """Readiness de solo lectura; nunca crea extensiones ni tablas."""
        try:
            result = await db.execute(text("SELECT 1"))
            if result.scalar() != 1:
                raise HTTPException(status_code=503, detail="Base de datos no disponible")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=503, detail="Base de datos no disponible") from None
        return {"status": "ok", "environment": settings.ENVIRONMENT}

    return application


app = get_application()
