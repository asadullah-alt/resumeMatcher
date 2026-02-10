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

import json
from beanie.operators import In

def beautify_json(data):
    """Prints JSON in a formatted, readable way."""
    return json.dumps(data, indent=2, default=str)

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
    
    stats_map = {} # email -> {user_obj, jobs_count, improvements_count}
    
    print("\n" + "="*95)
    print(f"{'User Name':<40} | {'Processed Jobs':<15} | {'Improvements':<15} | {'Credits':<10}")
    print("="*95)

    found_any = False
    for user in users:
        # Ignore specific user
        if user.local and user.local.email == "asadullahbeg@gmail.com":
            continue
            
        display_name = "Unknown"
        email = None
        if user.local and user.local.email:
            display_name = user.local.email
            email = user.local.email
        elif user.google and user.google.name:
            display_name = f"{user.google.name} (Google)"
            email = user.google.email
        elif user.facebook and user.facebook.name:
            display_name = f"{user.facebook.name} (Facebook)"
            email = user.facebook.email
        elif user.linkedin and user.linkedin.name:
            display_name = f"{user.linkedin.name} (LinkedIn)"
            email = user.linkedin.email
        
        user_id_str = str(user.id)
        
        # Count ProcessedJob records
        job_count = await ProcessedJob.find(ProcessedJob.user_id == user_id_str).count()
        
        # Count Improvement records
        user_resumes = await Resume.find(Resume.user_id == user_id_str).to_list()
        resume_ids = [str(r.resume_id) for r in user_resumes]
        
        improvement_count = 0
        if resume_ids:
            improvement_count = await Improvement.find(In(Improvement.resume_id, resume_ids)).count()
            
        if job_count > 0 or improvement_count > 0:
            found_any = True
            print(f"{display_name:<40} | {job_count:<15} | {improvement_count:<15} | {user.credits_remaining:<10}")
            if email:
                stats_map[email.lower()] = {
                    "user": user,
                    "display_name": display_name,
                    "job_count": job_count,
                    "improvement_count": improvement_count,
                    "resume_ids": resume_ids
                }

    if not found_any:
        print("No users found with ProcessedJob or Improvement records.")
        client.close()
        return

    print("="*95)

    while True:
        print("\nEnter a user email to see details (or 'exit' to quit):")
        target_email = input("> ").strip().lower()
        
        if target_email == 'exit':
            break
            
        if target_email not in stats_map:
            print(f"Error: No records found for email '{target_email}'. Please try again.")
            continue
            
        user_data = stats_map[target_email]
        print(f"\nUser: {user_data['display_name']}")
        print("What details would you like to see?")
        print("1. Processed Jobs")
        print("2. Improvements")
        print("3. Back to main menu")
        
        choice = input("Choice (1/2/3): ").strip()
        
        if choice == '1':
            jobs = await ProcessedJob.find(ProcessedJob.user_id == str(user_data['user'].id)).to_list()
            print(f"\n--- Processed Jobs for {target_email} ---")
            for i, job in enumerate(jobs, 1):
                print(f"\nJob #{i}:")
                # Beautify some key fields
                details = {
                    "job_title": job.job_title,
                    "company": job.company_profile.companyName if job.company_profile else "N/A",
                    "url": job.job_url,
                    "processed_at": job.processed_at
                }
                print(beautify_json(details))
                
        elif choice == '2':
            if not user_data['resume_ids']:
                print("\nNo improvements found for this user.")
                continue
                
            improvements = await Improvement.find(In(Improvement.resume_id, user_data['resume_ids'])).to_list()
            print(f"\n--- Improvements for {target_email} ---")
            for i, improvement in enumerate(improvements, 1):
                print(f"\nImprovement #{i}:")
                details = {
                    "resume_id": improvement.resume_id,
                    "job_id": improvement.job_id,
                    "original_score": improvement.original_score,
                    "new_score": improvement.new_score,
                    "created_at": improvement.created_at
                }
                print(beautify_json(details))
        
        elif choice == '3':
            continue
        else:
            print("Invalid choice.")

    client.close()

if __name__ == "__main__":
    asyncio.run(get_user_stats())
