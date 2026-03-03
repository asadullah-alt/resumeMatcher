import asyncio
import logging
import sys
import os

# Add the root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import init_db, close_db
from job_processor.models.job import UserJobMatch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    logger.info("Starting migration for UserJobMatch documents...")
    await init_db()
    
    try:
        # Find all documents where any of the new fields are missing
        # Mongodb query to check if fields exist
        query = {
            "$or": [
                {"clicked": {"$exists": False}},
                {"clicked_on_applied": {"$exists": False}},
                {"new_matched_job": {"$exists": False}}
            ]
        }
        
        matches = await UserJobMatch.find(query).to_list()
        logger.info(f"Found {len(matches)} documents requiring migration.")
        
        count = 0
        for match in matches:
            updated = False
            if not hasattr(match, "clicked") or match.clicked is None:
                match.clicked = False
                updated = True
            
            if not hasattr(match, "clicked_on_applied") or match.clicked_on_applied is None:
                match.clicked_on_applied = False
                updated = True
                
            if not hasattr(match, "new_matched_job") or match.new_matched_job is None:
                # Existing matches are considered "old", so we set new_matched_job to False
                match.new_matched_job = False
                updated = True
            
            if updated:
                await match.save()
                count += 1
        
        logger.info(f"Migration completed. Updated {count} documents.")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(migrate())
