"""Interfaz de almacenamiento de archivos y implementación local."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import UUID

logger = logging.getLogger("app.storage")


class FileStorage(Protocol):
    """Abstracción del almacenamiento de archivos (ADR-009)."""

    async def save(self, organization_id: UUID, content: bytes, filename: str) -> str: ...

    async def open(self, storage_path: str) -> BinaryIO: ...

    async def delete(self, storage_path: str) -> None: ...


class LocalFileStorage:
    """Almacenamiento local con rutas generadas por el sistema.

    La ruta relativa es ``{organization_id}/{uuid}.{extensión}`` bajo la raíz
    configurada. Los nombres nunca provienen del cliente, lo que evita
    path traversal.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    def _resolve(self, storage_path: str) -> Path:
        candidate = (self._root / storage_path).resolve()
        if not candidate.is_relative_to(self._root):
            raise ValueError("Ruta de almacenamiento fuera de la raíz permitida.")
        return candidate

    async def save(self, organization_id: UUID, content: bytes, filename: str) -> str:
        extension = Path(filename).suffix.lower()
        storage_path = f"{organization_id}/{uuid.uuid4()}{extension}"
        target = self._resolve(storage_path)

        def _write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        await asyncio.to_thread(_write)
        return storage_path

    async def open(self, storage_path: str) -> BinaryIO:
        path = self._resolve(storage_path)
        if not path.is_file():
            raise FileNotFoundError(storage_path)
        file: BinaryIO = await asyncio.to_thread(open, path, "rb")
        return file

    async def delete(self, storage_path: str) -> None:
        path = self._resolve(storage_path)

        def _delete() -> None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "archivo_no_eliminado", extra={"storage_path": storage_path}
                )

        await asyncio.to_thread(_delete)
