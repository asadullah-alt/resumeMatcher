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
            # We don't need hasattr checks because Beanie populates defaults in the object,
            # but they might still be missing in the DB.
            # Since the query already filtered for documents missing at least one field,
            # we can just set them to the desired values and save.
            
            # For migration of older records:
            match.clicked = getattr(match, 'clicked', False)
            match.clicked_on_applied = getattr(match, 'clicked_on_applied', False)
            # Legacy records should be considered "seen" (new_matched_job=False) 
            # as they are existing historical data.
            match.new_matched_job = False
            
            await match.save()
            count += 1
        
        logger.info(f"Migration completed. Updated {count} documents.")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(migrate())
