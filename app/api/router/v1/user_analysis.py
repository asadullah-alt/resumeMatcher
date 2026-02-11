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
import email.utils
import uuid

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

EMAIL_TEMPLATE_NO_RESUME_NO_JOBS = """
<!DOCTYPE html>
<html>
<head>
    <style>
        .container {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background-color: #2196F3; color: white; padding: 10px; text-align: center; }}
        .content {{ padding: 20px; }}
        .footer {{ font-size: 0.8em; color: #777; text-align: center; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>Action Required: Upload Your Resume</h1></div>
        <div class="content">
            <p>Hello,</p>
            <p>It looks like you haven't uploaded your resume. In order to use our free premium tool you need to upload your resume.</p>
            <p>Uploading your resume allows us to provide personalized job matching and AI-powered improvements.</p>
            <p>Best regards,<br>The Support Team</p>
        </div>
        <div class="footer"><p>&copy; 2026 Bhai Kaam Do</p></div>
    </div>
</body>
</html>
"""

EMAIL_TEMPLATE_NO_RESUME_WITH_JOBS = """
<!DOCTYPE html>
<html>
<head>
    <style>
        .container {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background-color: #2196F3; color: white; padding: 10px; text-align: center; }}
        .content {{ padding: 20px; }}
        .footer {{ font-size: 0.8em; color: #777; text-align: center; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>Complete Your Profile to Improve Your CV</h1></div>
        <div class="content">
            <p>Hello,</p>
            <p>It looks like you haven't uploaded your resume. Your processed jobs are saved, but you need to upload a CV so our system can improve it according to the job.</p>
            <p>Once you upload your resume, we can automatically tailor it for the jobs you've already found!</p>
            <p>Best regards,<br>The Support Team</p>
        </div>
        <div class="footer"><p>&copy; 2026 Bhai Kaam Do</p></div>
    </div>
</body>
</html>
"""

EMAIL_TEMPLATE_FEEDBACK = """
<!DOCTYPE html>
<html>
<head>
    <style>
        .container {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background-color: #607D8B; color: white; padding: 10px; text-align: center; }}
        .content {{ padding: 20px; }}
        .footer {{ font-size: 0.8em; color: #777; text-align: center; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>We Value Your Feedback</h1></div>
        <div class="content">
            <p>Hello,</p>
            <p>If there is anything which you don't like please feel free to contact us at <strong>support@bhaikaamdo.com</strong>. We take every feedback extremely seriously.</p>
            <p>Your input helps us build a better tool for everyone.</p>
            <p>Best regards,<br>The Support Team</p>
        </div>
        <div class="footer"><p>&copy; 2026 Bhai Kaam Do</p></div>
    </div>
</body>
</html>
"""

EMAIL_TEMPLATE_FOMO_PROMOTION = """
<!DOCTYPE html>
<html>
<head>
    <style>
        .container {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            line-height: 1.6; 
            color: #2c3e50; 
            max-width: 600px; 
            margin: 0 auto; 
            text-align: center;
            border: 1px solid #eee;
            border-radius: 10px;
            overflow: hidden;
        }}
        .header {{ 
            background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%); 
            color: white; 
            padding: 40px 20px; 
        }}
        .content {{ padding: 40px 30px; }}
        .footer {{ 
            font-size: 0.85em; 
            color: #95a5a6; 
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .highlight {{ color: #e74c3c; font-weight: bold; font-size: 1.25em; }}
        .cta-button {{
            display: inline-block;
            padding: 15px 35px;
            background-color: #ff4b2b;
            color: white !important;
            text-decoration: none;
            border-radius: 30px;
            font-weight: bold;
            margin-top: 25px;
            box-shadow: 0 4px 15px rgba(255, 75, 43, 0.3);
        }}
        h1 {{ margin-top: 0; font-size: 2.2em; }}
        .urgent {{ background-color: #fff3f3; padding: 10px; border-radius: 5px; border: 1px dashed #ff4b2b; display: inline-block; margin: 15px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Don't Stay Behind! 🚀</h1>
        </div>
        <div class="content">
            <p style="font-size: 1.1em;">Did you know?</p>
            <p><span class="highlight">Tailor-making your resume</span> for each job application can increase your chances of landing an interview by <span class="highlight">40%</span>!</p>
            
            <p>You haven't used your premium credits yet, and we want to help you land that dream job.</p>
            
            <div class="urgent">
               Our premium tailoring service is <strong>FREE</strong> for a very limited time!
            </div>
            
            <p>This is your chance to use our high-end AI tool to perfectly align your profile with the job requirements. Don't let this opportunity slip away.</p>
            
            <a href="https://bhaikaamdo.com" class="cta-button">Avail This Chance Now</a>
            
            <p style="margin-top: 30px; font-style: italic; color: #7f8c8d;">Acting fast is the first step toward your new career.</p>
        </div>
        <div class="footer">
            <p>&copy; 2026 Bhai Kaam Do Support Team</p>
            <p>You received this because you are a valued member of our community.</p>
        </div>
    </div>
</body>
</html>
"""

router = APIRouter()

class UserStats(BaseModel):
    user_email: str
    processed_jobs_count: int
    improvements_count: int
    resumes_count: int
    credits_remaining: int

class AddCreditsRequest(BaseModel):
    user_email: EmailStr

class AddCreditsResponse(BaseModel):
    message: str
    new_credits: int

class NotificationRequest(BaseModel):
    user_email: str
    template_type: str  # "no_resume", "no_resume_with_jobs", "feedback", "fomo_promotion"

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

def send_notification_email(to_email: str, template: str, subject: str):
    """Sends an HTML notification email with improved deliverability headers."""
    msg = MIMEMultipart()
    
    # Standard Headers
    msg['From'] = f"Bhai Kaam Do Support <{EMAIL_USER}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Message-ID'] = email.utils.make_msgid(domain='bhaikaamdo.com')
    
    # Deliverability/Spam Prevention Headers
    msg['List-Unsubscribe'] = f"<mailto:support@bhaikaamdo.com?subject=Unsubscribe%20{to_email}>"
    msg['Precedence'] = 'bulk'
    msg['X-Auto-Response-Suppress'] = 'All'
    
    msg.attach(MIMEText(template, 'html'))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Successfully sent notification email to {to_email} with subject: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")

def send_credit_notification_email(to_email: str, credits_added: int):
    """Sends an HTML notification email for credits."""
    subject = "Credits Added to Your Account"
    template = EMAIL_TEMPLATE_LIVE.format(credits_added=credits_added)
    send_notification_email(to_email, template, subject)

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
            resumes_count=len(user_resumes),
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
    
    send_credit_notification_email(request.user_email, 50)
    
    return AddCreditsResponse(
        message=f"Added 50 credits to {request.user_email}",
        new_credits=target_user.credits_remaining
    )

@router.post("/send-notification")
async def trigger_notification(request: NotificationRequest, admin: User = Depends(get_admin_user)):
    if request.template_type == "no_resume":
        template = EMAIL_TEMPLATE_NO_RESUME_NO_JOBS
        subject = "Quick reminder: Upload your resume"
    elif request.template_type == "no_resume_with_jobs":
        template = EMAIL_TEMPLATE_NO_RESUME_WITH_JOBS
        subject = "Next step: Improve your CV with your matches"
    elif request.template_type == "feedback":
        template = EMAIL_TEMPLATE_FEEDBACK
        subject = "We'd love to hear your thoughts"
    elif request.template_type == "fomo_promotion":
        template = EMAIL_TEMPLATE_FOMO_PROMOTION
        subject = "🔥 Secret to 40% more interviews (Limited Time Free!)"
    else:
        raise HTTPException(status_code=400, detail="Invalid template type")
    
    send_notification_email(request.user_email, template, subject)
    return {"message": f"Notification '{request.template_type}' sent to {request.user_email}"}
