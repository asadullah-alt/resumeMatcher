import asyncio
import os
import sys

# Add the current directory to sys.path to allow imports from 'app'
sys.path.append(os.path.abspath(os.curdir))

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings
from app.models.user import User
from app.models.job import ProcessedJob, Job
from app.models.improvement import Improvement
from app.models.resume import Resume, ProcessedResume, ImprovedResume
from app.models.cover_letter import CoverLetter

async def get_user_stats():
    # Initialize MongoDB client
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]
    
    # Initialize Beanie
    await init_beanie(
        database=db,
        document_models=[
            User, 
            ProcessedJob, 
            Improvement, 
            Resume, 
            Job, 
            ProcessedResume, 
            ImprovedResume,
            CoverLetter
        ]
    )
    
    # Fetch all users
    users = await User.find_all().to_list()
    
    stats = []
    
    for user in users:
        # Determine display name
        display_name = "Unknown"
        if user.local and user.local.email:
            display_name = user.local.email
        elif user.google and user.google.name:
            display_name = f"{user.google.name} (Google)"
        elif user.facebook and user.facebook.name:
            display_name = f"{user.facebook.name} (Facebook)"
        elif user.linkedin and user.linkedin.name:
            display_name = f"{user.linkedin.name} (LinkedIn)"
        
        user_id_str = str(user.id)
        
        # Count ProcessedJob records
        job_count = await ProcessedJob.find(ProcessedJob.user_id == user_id_str).count()
        
        # Count Improvement records
        # Improvements are linked via resume_id. We need to find the user's resumes first.
        user_resumes = await Resume.find(Resume.user_id == user_id_str).to_list()
        resume_ids = [str(r.resume_id) for r in user_resumes]
        
        improvement_count = 0
        if resume_ids:
            improvement_count = await Improvement.find(In(Improvement.resume_id, resume_ids)).count()
            
        # Only include users who have at least one record
        if job_count > 0 or improvement_count > 0:
            stats.append({
                "name": display_name,
                "jobs": job_count,
                "improvements": improvement_count
            })
            
    # Print results
    if not stats:
        print("No users found with ProcessedJob or Improvement records.")
    else:
        print(f"{'User Name':<40} | {'Processed Jobs':<15} | {'Improvements':<15}")
        print("-" * 76)
        for entry in stats:
            print(f"{entry['name']:<40} | {entry['jobs']:<15} | {entry['improvements']:<15}")

    client.close()

from beanie.operators import In

if __name__ == "__main__":
    asyncio.run(get_user_stats())
