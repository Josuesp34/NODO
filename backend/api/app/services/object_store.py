"""Archivos privados, claves acotadas por atleta y errores sin credenciales."""

import asyncio
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx

from app.core.config import settings


class ObjectStoreError(Exception):
    pass


def valid_key(key: str) -> str:
    if not re.fullmatch(r"(?:fit|export)/[1-9]\d*/[a-f0-9]{64}\.(?:fit|json)", key):
        raise ObjectStoreError("Clave de archivo inválida")
    return key


def enabled() -> bool:
    return getattr(settings, "STORAGE_BACKEND", "none") != "none"


def local_root() -> Path:
    path = getattr(settings, "STORAGE_LOCAL_PATH", "")
    if settings.ENVIRONMENT != "development" or not path or not Path(path).is_absolute():
        raise ObjectStoreError("Almacenamiento local sólo disponible en demo development")
    return Path(path).resolve()


def local_target(key: str) -> Path:
    root = str(local_root())
    target = os.path.realpath(os.path.join(root, key))
    if not target.startswith(root + os.sep):
        raise ObjectStoreError("Archivo fuera del almacenamiento privado")
    return Path(target)


async def authorization() -> dict[str, str]:
    def token():
        import google.auth
        from google.auth.transport.requests import Request

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/devstorage.read_write"])
        if not credentials.valid:
            credentials.refresh(Request())
        return credentials.token

    try:
        return {"Authorization": "Bearer " + await asyncio.to_thread(token)}
    except Exception:
        raise ObjectStoreError("Identidad de almacenamiento no disponible") from None


def bucket_url() -> str:
    bucket = getattr(settings, "STORAGE_BUCKET", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]", bucket):
        raise ObjectStoreError("Bucket privado no configurado")
    return f"https://storage.googleapis.com/storage/v1/b/{bucket}/o"


async def put_file(key: str, content: bytes) -> None:
    valid_key(key)
    if len(content) > settings.MAX_FIT_BYTES:
        raise ObjectStoreError("Archivo demasiado grande")
    if getattr(settings, "STORAGE_BACKEND", "none") == "local":
        target = local_target(key)

        def write():
            temporary = None
            try:
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                if target.exists() and target.stat().st_size == len(content) and target.read_bytes() == content:
                    return
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(content)
                temporary.replace(target)
            except OSError:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
                raise ObjectStoreError("No se pudo guardar el archivo privado") from None

        await asyncio.to_thread(write)
        return
    if getattr(settings, "STORAGE_BACKEND", "none") != "gcs":
        raise ObjectStoreError("Almacenamiento privado no configurado")
    url = bucket_url().replace("/storage/v1/", "/upload/storage/v1/")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            result = await client.post(
                url,
                params={"uploadType": "media", "name": key, "ifGenerationMatch": "0"},
                content=content,
                headers={**await authorization(), "Content-Type": "application/octet-stream"},
            )
            if result.status_code != 412:  # El mismo hash ya existe; no renueva su retención.
                result.raise_for_status()
    except (httpx.HTTPError, ObjectStoreError):
        raise ObjectStoreError("No se pudo guardar el archivo privado") from None


async def read_file(key: str) -> bytes:
    valid_key(key)
    if getattr(settings, "STORAGE_BACKEND", "none") == "local":
        target = local_target(key)
        try:
            with target.open("rb") as stream:
                content = stream.read(settings.MAX_FIT_BYTES + 1)
        except OSError:
            raise ObjectStoreError("Archivo no disponible") from None
        if len(content) > settings.MAX_FIT_BYTES:
            raise ObjectStoreError("Archivo demasiado grande")
        return content
    if getattr(settings, "STORAGE_BACKEND", "none") != "gcs":
        raise ObjectStoreError("Almacenamiento privado no configurado")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream(
                "GET", bucket_url() + "/" + quote(key, safe=""), params={"alt": "media"}, headers=await authorization()
            ) as result:
                result.raise_for_status()
                chunks = bytearray()
                async for chunk in result.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > settings.MAX_FIT_BYTES:
                        raise ObjectStoreError("Archivo demasiado grande")
                return bytes(chunks)
    except httpx.HTTPError:
        raise ObjectStoreError("Archivo no disponible") from None


async def delete_file(key: str, generation: str | None = None) -> None:
    valid_key(key)
    if getattr(settings, "STORAGE_BACKEND", "none") == "local":
        local_target(key).unlink(missing_ok=True)
        return
    if getattr(settings, "STORAGE_BACKEND", "none") != "gcs":
        raise ObjectStoreError("Almacenamiento privado no configurado")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            result = await client.delete(
                bucket_url() + "/" + quote(key, safe=""),
                params={"generation": generation} if generation is not None else {},
                headers=await authorization(),
            )
            if result.status_code != 404:
                result.raise_for_status()
    except httpx.HTTPError:
        raise ObjectStoreError("No se pudo eliminar el archivo privado") from None


async def inventory(prefix: str):
    if not re.fullmatch(r"(?:fit|export)/(?:[1-9]\d*/)?", prefix):
        raise ObjectStoreError("Prefijo de archivo inválido")
    if getattr(settings, "STORAGE_BACKEND", "none") == "local":
        root = local_root()
        for path in local_target(prefix).rglob("*"):
            if path.is_file():
                yield path.relative_to(root).as_posix(), datetime.fromtimestamp(path.stat().st_mtime, UTC), None
        return
    if getattr(settings, "STORAGE_BACKEND", "none") != "gcs":
        if settings.ENVIRONMENT != "development":
            raise ObjectStoreError("Almacenamiento privado no configurado")
        return
    page = None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                params = {"prefix": prefix, "maxResults": "1000", "versions": "true"}
                if page:
                    params["pageToken"] = page
                result = await client.get(bucket_url(), params=params, headers=await authorization())
                result.raise_for_status()
                payload = result.json()
                for item in payload.get("items", []):
                    yield (
                        item["name"],
                        datetime.fromisoformat(item.get("timeCreated", item["updated"]).replace("Z", "+00:00")),
                        item["generation"],
                    )
                page = payload.get("nextPageToken")
                if not page:
                    break
    except (httpx.HTTPError, KeyError, ValueError):
        raise ObjectStoreError("No se pudo revisar el almacenamiento privado") from None


async def delete_athlete_files(athlete_id: int) -> int:
    if athlete_id < 1:
        raise ObjectStoreError("Atleta inválido")
    count = 0
    for kind in ("fit", "export"):
        async for key, _, generation in inventory(f"{kind}/{athlete_id}/"):
            await delete_file(key, generation)
            count += 1
    return count


async def prune_expired_files(before: datetime, export_before: datetime | None = None) -> int:
    if before.tzinfo is None or (export_before is not None and export_before.tzinfo is None):
        raise ObjectStoreError("Retención requiere fecha con zona horaria")
    count = 0
    for kind in ("fit", "export"):
        async for key, updated, generation in inventory(f"{kind}/"):
            if updated < (export_before if kind == "export" and export_before is not None else before):
                await delete_file(key, generation)
                count += 1
    return count
