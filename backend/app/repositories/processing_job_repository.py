"""Repositorio de jobs de procesamiento documental."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import JobStatus, JobType
from app.models.processing_job import ProcessingJob

INTERRUPTED_MESSAGE = "Interrumpido por reinicio del proceso"


class ProcessingJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, job_id: uuid.UUID) -> ProcessingJob | None:
        return await self._session.get(ProcessingJob, job_id)

    async def get_active_for_document(self, document_id: uuid.UUID) -> ProcessingJob | None:
        result = await self._session.execute(
            select(ProcessingJob).where(
                ProcessingJob.document_id == document_id,
                ProcessingJob.status.in_((JobStatus.PENDING, JobStatus.PROCESSING)),
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
        job_type: JobType = JobType.INGEST,
    ) -> ProcessingJob:
        job = ProcessingJob(
            document_id=document_id,
            organization_id=organization_id,
            job_type=job_type,
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def claim(self, job_id: uuid.UUID) -> bool:
        """Transición atómica ``PENDING -> PROCESSING`` con ``attempts + 1``."""
        result = await self._session.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id, ProcessingJob.status == JobStatus.PENDING)
            .values(
                status=JobStatus.PROCESSING,
                attempts=ProcessingJob.attempts + 1,
                started_at=func.now(),
            )
        )
        await self._session.commit()
        return result.rowcount == 1

    async def mark_stale_as_failed(self) -> int:
        """Marca ``FAILED`` los jobs huérfanos al reiniciar el proceso."""
        result = await self._session.execute(
            update(ProcessingJob)
            .where(ProcessingJob.status.in_((JobStatus.PENDING, JobStatus.PROCESSING)))
            .values(
                status=JobStatus.FAILED,
                error_message=INTERRUPTED_MESSAGE,
                completed_at=func.now(),
            )
        )
        return result.rowcount
