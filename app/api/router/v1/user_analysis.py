from fastapi import APIRouter, Header, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from app.models.user import User
from app.models.job import ProcessedJob
from app.models.improvement import Improvement
from app.models.resume import Resume
from beanie.operators import In
import logging
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger(__name__)

# Email configuration
EMAIL_USER = os.getenv('EMAIL_USER', 'support@bhaikaamdo.com')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'Apogee12345!')
SMTP_SERVER = 'smtpout.secureserver.net'
SMTP_PORT = 587
EMAIL_TEMPLATE_LIVE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        .container {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background-color: #4CAF50; color: white; padding: 10px; text-align: center; }}
        .content {{ padding: 20px; }}
        .footer {{ font-size: 0.8em; color: #777; text-align: center; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>Credits Added!</h1></div>
        <div class="content">
            <p>Hello,</p>
            <p>We've added <strong>{credits_added}</strong> credits to your account.</p>
            <p>You can now continue using our premium services.</p>
            <p>Best regards,<br>The Support Team</p>
        </div>
        <div class="footer"><p>&copy; 2026 Bhai Kaam Do</p></div>
    </div>
</body>
</html>
"""

router = APIRouter()

class UserStats(BaseModel):
    user_email: str
    processed_jobs_count: int
    improvements_count: int
    credits_remaining: int

class AddCreditsRequest(BaseModel):
    user_email: EmailStr

class AddCreditsResponse(BaseModel):
    message: str
    new_credits: int

async def get_admin_user(
    x_admin_email: str = Header(..., alias="X-Admin-Email"),
    x_admin_token: str = Header(..., alias="X-Admin-Token")
):
    # Requirement: only authenticates if local.email is 'asadullahbeg' 
    # and token is the one in local.token for that user
    if x_admin_email != "asadullahbeg@gmail.com":
        raise HTTPException(status_code=403, detail="Unauthorized: Only asadullahbeg can access this API.")
    
    admin = await User.find_one({"local.email": "asadullahbeg@gmail.com"})
    if not admin or not admin.local or admin.local.token != x_admin_token:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid token or user not found.")
    
    return admin

def send_notification_email(to_email: str, credits_added: int):
    """Sends an HTML notification email using GoDaddy SMTP."""
    subject = "Credits Added to Your Account"
    body = EMAIL_TEMPLATE_LIVE.format(credits_added=credits_added)
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Upgrade to secure connection
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Successfully sent credit notification email to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")

@router.get("/stats", response_model=List[UserStats])
async def get_all_users_stats(admin: User = Depends(get_admin_user)):
    users = await User.find_all().to_list()
    
    all_stats = []
    for user in users:
        email = "Unknown"
        if user.local:
            email = user.local.email
        elif user.google:
            email = user.google.email
        elif user.facebook:
            email = user.facebook.email
        elif user.linkedin:
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
            
        all_stats.append(UserStats(
            user_email=email,
            processed_jobs_count=job_count,
            improvements_count=improvement_count,
            credits_remaining=user.credits_remaining
        ))
        
    return all_stats

@router.post("/add-credits", response_model=AddCreditsResponse)
async def add_credits(request: AddCreditsRequest, admin: User = Depends(get_admin_user)):
    target_user = await User.find_one({"local.email": request.user_email})
    if not target_user:
        # Check other auth methods if local email not found
        target_user = await User.find_one({"google.email": request.user_email})
    if not target_user:
        target_user = await User.find_one({"facebook.email": request.user_email})
    if not target_user:
        target_user = await User.find_one({"linkedin.email": request.user_email})
        
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    target_user.credits_remaining += 50
    await target_user.save()
    
    send_notification_email(request.user_email, 50)
    
    return AddCreditsResponse(
        message=f"Added 50 credits to {request.user_email}",
        new_credits=target_user.credits_remaining
    )
