"""Interfaz de cola de procesamiento y implementación temporal con BackgroundTasks."""

import uuid
from typing import Protocol

from fastapi import BackgroundTasks

from app.services.processing_service import run_processing_job


class ProcessingQueue(Protocol):
    """Abstracción de la cola de procesamiento (ADR-004)."""

    async def enqueue_ingestion(self, document_id: uuid.UUID, job_id: uuid.UUID) -> None: ...

    async def enqueue_reprocess(self, document_id: uuid.UUID, job_id: uuid.UUID) -> None: ...


class FastAPIProcessingQueue:
    """Implementación temporal **no durable** sobre ``BackgroundTasks``.

    Si el proceso se reinicia, los trabajos pueden perderse. Se compensa con
    reconciliación al arranque, idempotencia por documento y reproceso manual.
    """

    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self._background_tasks = background_tasks

    async def enqueue_ingestion(self, document_id: uuid.UUID, job_id: uuid.UUID) -> None:
        self._background_tasks.add_task(run_processing_job, document_id, job_id)

    async def enqueue_reprocess(self, document_id: uuid.UUID, job_id: uuid.UUID) -> None:
        self._background_tasks.add_task(run_processing_job, document_id, job_id)
