import asyncio
import logging
import sys
from Project_artemis.db.connection import init_db
from Project_artemis.services.watcher import job_watcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(name)s - %(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("Project_artemis")

async def main():
    logger.info("Starting Project Artemis Service...")
    
    # Initialize database and beanie
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return

    # Start the job watcher
    try:
        await job_watcher.watch_jobs()
    except KeyboardInterrupt:
        logger.info("Service stopping...")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
