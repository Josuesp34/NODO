"""Ejecutar explícitamente: python -m app.create_tables (solo desarrollo)."""
import asyncio

from app.core.database import engine, init_db


async def main():
    try:
        await init_db()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
