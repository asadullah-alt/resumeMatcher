import asyncio
import motor.motor_asyncio
from beanie import init_beanie
from job_processor.config import Config
from job_processor.models.job import Job, ProcessedOpenJobs, OpenJobsVector
from job_processor.services.processor import JobProcessor
from job_processor.logger import get_logger

logger = get_logger("job_processor.main")

async def watch_jobs():
    """
    Listens to the 'ProcessedOpenJobs' collection for new insertions or changes.
    Matches the corresponding 'Job' document via job_id.
    """
    logger.info(f"Connecting to MongoDB: {Config.MONGO_URI}, DB='{Config.DB_NAME}'")
    client = motor.motor_asyncio.AsyncIOMotorClient(Config.MONGO_URI)
    db = client[Config.DB_NAME]
    
    # Initialize Beanie
    await init_beanie(database=db, document_models=[Job, ProcessedOpenJobs, OpenJobsVector])
    logger.info("Beanie initialized — models: Job, ProcessedOpenJobs, OpenJobsVector")
    
    processor = JobProcessor()
    logger.info("Service started. Listening for changes in ProcessedOpenJobs...")

    # Change Stream for ProcessedOpenJobs collection
    async with db["ProcessedOpenJobs"].watch([
        {"$match": {"operationType": {"$in": ["insert", "update", "replace"]}}}
    ]) as stream:
        async for change in stream:
            op_type = change.get("operationType", "unknown")

            # In 'insert', the doc is in fullDocument. 
            # In 'update', we might need to fetch the full document or it might be in fullDocument if configured.
            processed_data = change.get("fullDocument")
            
            if not processed_data:
                doc_id = change["documentKey"]["_id"]
                logger.debug(f"[op={op_type}] fullDocument absent — fetching by _id: {doc_id}")
                processed_doc = await ProcessedOpenJobs.get(doc_id)
                if not processed_doc:
                    logger.warning(f"[op={op_type}] Could not find ProcessedOpenJobs document for _id: {doc_id} — skipping")
                    continue
            else:
                processed_doc = ProcessedOpenJobs(**processed_data)

            job_id = processed_doc.job_id
            logger.info(f"[op={op_type}] Change detected in ProcessedOpenJobs for job_id: {job_id}")
            
            # Fetch the corresponding Job document
            source_job = await Job.find_one(Job.job_id == job_id)
            
            if not source_job:
                logger.warning(f"[Job {job_id}] Corresponding Job document not found — skipping")
                continue

            try:
                await processor.process_new_job(source_job, processed_doc)
            except Exception as e:
                logger.error(f"[Job {job_id}] Processing failed: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(watch_jobs())
    except KeyboardInterrupt:
        logger.info("Service stopped by user (KeyboardInterrupt)")
