import uuid
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from job_processor.config import Config
from job_processor.logger import get_logger

logger = get_logger("job_processor.qdrant_service")

# Deterministic namespace for converting string job_ids to UUIDs
_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # UUID_DNS namespace


def _job_uuid(job_id: str) -> str:
    """Derives a deterministic UUID from a string job_id using uuid5."""
    return str(uuid.uuid5(_NAMESPACE, job_id))


class QdrantService:
    def __init__(self):
        logger.info(f"Connecting to Qdrant at {Config.QDRANT_HOST}:{Config.QDRANT_PORT}")
        self.client = QdrantClient(host=Config.QDRANT_HOST, port=Config.QDRANT_PORT)
        self.job_collection = Config.QDRANT_JOB_COLLECTION
        self.resume_collection = Config.QDRANT_RESUME_COLLECTION
        self._ensure_collections()

    def _ensure_collections(self):
        """Creates the Qdrant collections if they do not already exist."""
        existing = [c.name for c in self.client.get_collections().collections]
        
        for collection in [self.job_collection, self.resume_collection]:
            if collection in existing:
                logger.info(f"Qdrant collection '{collection}' already exists — skipping creation")
                continue

            logger.info(f"Creating Qdrant collection '{collection}' ...")
            self.client.create_collection(
                collection_name=collection,
                vectors_config={
                    "dense": qmodels.VectorParams(
                        size=Config.QDRANT_DENSE_DIM,
                        distance=qmodels.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": qmodels.SparseVectorParams(
                        index=qmodels.SparseIndexParams(on_disk=False)
                    )
                },
            )
            logger.info(f"Qdrant collection '{collection}' created successfully")

    def upsert_vector(
        self,
        collection_name: str,
        entity_id: str,
        dense_vector: List[float],
        sparse_vector: Dict[str, Any],
        payload: Dict[str, Any],
    ):
        """
        Upserts a vector point into a specified Qdrant collection.

        Args:
            collection_name: Name of the Qdrant collection.
            entity_id:       Original string ID (job_id or resume_id).
            dense_vector:    List[float] from VectorService.
            sparse_vector:   Dict with 'indices' and 'values' from VectorService.
            payload:         Arbitrary metadata stored alongside the vector.
        """
        point_id = _job_uuid(entity_id)

        sparse = qmodels.SparseVector(
            indices=sparse_vector["indices"],
            values=sparse_vector["values"],
        )

        point = qmodels.PointStruct(
            id=point_id,
            vector={"dense": dense_vector, "sparse": sparse},
            payload=payload,
        )

        self.client.upsert(
            collection_name=collection_name,
            points=[point],
        )
        logger.info(
            f"Qdrant upsert OK — collection={collection_name}, entity_id={entity_id!r}, point_id={point_id}, "
            f"dense_dim={len(dense_vector)}, sparse_tokens={len(sparse_vector['indices'])}"
        )
    def point_exists(self, collection_name: str, entity_id: str) -> bool:
        """Checks if a point with the derived UUID exists in the collection."""
        point_id = _job_uuid(entity_id)
        try:
            results = self.client.retrieve(
                collection_name=collection_name,
                ids=[point_id],
                with_payload=False,
                with_vectors=False,
            )
            return len(results) > 0
        except Exception as e:
            logger.error(f"Error checking point existence in Qdrant: {e}")
            return False

    def get_point_by_id(self, collection_name: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a point (including vectors) by its original entity ID."""
        point_id = _job_uuid(entity_id)
        try:
            results = self.client.retrieve(
                collection_name=collection_name,
                ids=[point_id],
                with_payload=True,
                with_vectors=True,
            )
            if results:
                return {
                    "payload": results[0].payload,
                    "vectors": results[0].vector
                }
            return None
        except Exception as e:
            logger.error(f"Error retrieving point from Qdrant: {e}")
            return None

    def search_jobs(self, dense_vector: List[float], sparse_vector: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        """
        Performs a hybrid search (dense + sparse) on the jobs collection.
        Uses Reciprocal Rank Fusion or simple score addition if not available.
        """
        try:
            sparse = qmodels.SparseVector(
                indices=sparse_vector["indices"],
                values=sparse_vector["values"],
            )

            results = self.client.query_points(
                collection_name=self.job_collection,
                prefetch=[
                    qmodels.Prefetch(
                        query=dense_vector,
                        using="dense",
                        limit=limit,
                    ),
                    qmodels.Prefetch(
                        query=sparse,
                        using="sparse",
                        limit=limit,
                    ),
                ],
                query=qmodels.FusionQuery(fusion=qmodels.Fusion.RRF),
                limit=limit,
            )

            output = []
            for hit in results.points:
                output.append({
                    "job_id": hit.payload.get("job_id"),
                    "score": hit.score,
                    "payload": hit.payload
                })
            return output
        except Exception as e:
            logger.error(f"Error searching Qdrant: {e}")
            return []
