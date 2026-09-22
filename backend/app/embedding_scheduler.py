from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.build_historical_embeddings import (
    get_all_historical_incidents,
)
from app.embedding_generation import (
    generate_historical_incident_embedding,
    historical_incident_to_text,
)
from app.vector_store import (
    collection,
    get_collection_count,
    get_stored_incident_ids,
    store_historical_incident,
)


logger = logging.getLogger(__name__)


DEFAULT_INTERVAL_HOURS = 24

EMBEDDING_REFRESH_INTERVAL_HOURS = int(
    os.getenv(
        "EMBEDDING_REFRESH_INTERVAL_HOURS",
        str(DEFAULT_INTERVAL_HOURS),
    )
)


scheduler = BackgroundScheduler(
    timezone="UTC"
)


def refresh_embedding_index() -> dict:
    """
    Incrementally refresh the ChromaDB historical incident index.

    Only incidents that are not already present in ChromaDB
    are embedded and stored.
    """

    started_at = datetime.now(timezone.utc)

    logger.info(
        "Starting periodic ChromaDB embedding refresh."
    )

    try:
        historical_incidents = (
            get_all_historical_incidents()
        )

        stored_ids = get_stored_incident_ids()

        new_incidents = [
            incident
            for incident in historical_incidents
            if str(incident.get("incident_id"))
            not in stored_ids
        ]

        successfully_embedded = 0

        for incident in new_incidents:

            incident_id = str(
                incident.get("incident_id")
            )

            try:
                document = historical_incident_to_text(
                    incident
                )

                embedding = (
                    generate_historical_incident_embedding(
                        incident
                    )
                )

                store_historical_incident(
                    incident=incident,
                    embedding=embedding,
                    document=document,
                )

                successfully_embedded += 1

                logger.info(
                    "Embedded new historical incident: %s",
                    incident_id,
                )

            except Exception:
                logger.exception(
                    "Failed to embed historical incident: %s",
                    incident_id,
                )

        collection_count = get_collection_count()

        completed_at = datetime.now(timezone.utc)

        result = {
            "status": "success",
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "historical_incidents": len(
                historical_incidents
            ),
            "existing_embeddings": len(
                stored_ids
            ),
            "new_incidents": len(
                new_incidents
            ),
            "successfully_embedded": (
                successfully_embedded
            ),
            "collection_count": collection_count,
        }

        logger.info(
            "Periodic embedding refresh completed: %s",
            result,
        )

        return result

    except Exception as exc:

        completed_at = datetime.now(timezone.utc)

        logger.exception(
            "Periodic embedding refresh failed."
        )

        return {
            "status": "failed",
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "error": str(exc),
        }

def validate_embedding_index() -> dict:
    """
    Validate ChromaDB vector-index health.

    ChromaDB maintains its vector index automatically when
    embeddings are inserted or updated. This check verifies that
    the collection is accessible, contains embeddings, and can
    execute a similarity query successfully.
    """

    started_at = datetime.now(timezone.utc)

    logger.info(
        "Starting ChromaDB index health check."
    )

    try:
        collection_count = collection.count()

        if collection_count == 0:
            result = {
                "status": "warning",
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "collection_count": 0,
                "message": "ChromaDB collection is empty.",
            }

            logger.warning(
                "ChromaDB index health check: collection is empty."
            )

            return result

        sample = collection.get(
            limit=1,
            include=["embeddings", "documents"],
        )

        ids = sample.get("ids", [])

        if not ids:
            raise RuntimeError(
                "ChromaDB collection contains records but "
                "no sample record could be retrieved."
            )

        embedding = sample.get("embeddings")

        if embedding is None:
            raise RuntimeError(
                "ChromaDB sample record has no embedding."
            )

        query_result = collection.query(
            query_embeddings=[embedding[0]],
            n_results=1,
        )

        query_ids = query_result.get("ids", [])

        if not query_ids:
            raise RuntimeError(
                "ChromaDB similarity query returned no results."
            )

        completed_at = datetime.now(timezone.utc)

        result = {
            "status": "success",
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "collection_count": collection_count,
            "sample_id": str(ids[0]),
            "query_verified": True,
        }

        logger.info(
            "ChromaDB index health check completed: %s",
            result,
        )

        return result

    except Exception as exc:
        completed_at = datetime.now(timezone.utc)

        logger.exception(
            "ChromaDB index health check failed."
        )

        return {
            "status": "failed",
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "error": str(exc),
        }
    
def start_embedding_scheduler() -> None:
    """
    Start the periodic embedding scheduler.
    """

    if scheduler.running:

        logger.info(
            "Embedding scheduler is already running."
        )

        return

    scheduler.add_job(
        refresh_embedding_index,
        trigger="interval",
        hours=EMBEDDING_REFRESH_INTERVAL_HOURS,
        id="historical_embedding_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()

    logger.info(
        "Embedding scheduler started. "
        "Refresh interval: %s hour(s).",
        EMBEDDING_REFRESH_INTERVAL_HOURS,
    )


def stop_embedding_scheduler() -> None:
    """
    Stop the periodic embedding scheduler.
    """

    if not scheduler.running:
        return

    scheduler.shutdown(
        wait=False
    )

    logger.info(
        "Embedding scheduler stopped."
    )