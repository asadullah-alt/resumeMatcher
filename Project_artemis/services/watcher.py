import asyncio
from ..db.models import Job
from .processor import job_processor
import logging

logger = logging.getLogger(__name__)

class JobWatcher:
    async def watch_jobs(self):
        logger.info("Starting Job collection watcher...")
        
        # Access the underlying motor collection for change streams
        collection = Job.get_motor_collection()
        
        pipeline = [
            {
                "$match": {
                    "operationType": "insert",
                    "fullDocument.public": True
                }
            }
        ]

        async with collection.watch(pipeline, full_document="updateLookup") as stream:
            logger.info("Watching for new public job postings...")
            async for change in stream:
                try:
                    full_doc = change.get("fullDocument")
                    if full_doc:
                        # Convert dict to Beanie Document
                        job = Job(**full_doc)
                        # Process the job asynchronously
                        asyncio.create_task(job_processor.process_job(job))
                except Exception as e:
                    logger.error(f"Error in change stream processing: {e}")

job_watcher = JobWatcher()
