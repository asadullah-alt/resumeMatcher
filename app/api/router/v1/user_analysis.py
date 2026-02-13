from fastapi import APIRouter, Header, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from app.models.user import User
from app.models.job import ProcessedJob
from app.models.improvement import Improvement
from app.models.resume import Resume, ProcessedResume
from app.models.cover_letter import CoverLetter
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
# SMTP2GO settings
SMTP_SERVER = 'mail-eu.smtp2go.com'
SMTP_PORT = 2525
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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Improve Your Success Rate - Bhai Kaam Do</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f4f4f4;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f4f4f4;">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 32px; font-weight: 700; line-height: 1.2;">
                                Don't Stay Behind
                            </h1>
                            <p style="margin: 10px 0 0 0; color: #ffffff; font-size: 18px; opacity: 0.95;">
                                Your Career Deserves the Best
                            </p>
                        </td>
                    </tr>

                    <!-- Main Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; color: #333333; font-size: 16px; line-height: 1.6;">
                                Dear valued user,
                            </p>
                            
                            <p style="margin: 0 0 20px 0; color: #333333; font-size: 16px; line-height: 1.6;">
                                Did you know that <strong>tailor-making your resume</strong> for each job application can increase your chances of landing an interview by <strong style="color: #667eea;">40%</strong>?
                            </p>

                            <p style="margin: 0 0 30px 0; color: #333333; font-size: 16px; line-height: 1.6;">
                                You haven't used your premium credits yet, and we want to help you land that dream job. We're excited to offer you a special opportunity.
                            </p>

                            <!-- Special Offer Section -->
                            <div style="background-color: #f8f9ff; border-left: 4px solid #667eea; padding: 20px; margin: 0 0 30px 0; border-radius: 4px;">
                                <h2 style="margin: 0 0 15px 0; color: #667eea; font-size: 20px; font-weight: 600;">
                                    Special Offer:
                                </h2>
                                <p style="margin: 0; color: #333333; font-size: 16px; line-height: 1.6;">
                                    Our premium tailoring service is <strong>FREE</strong> for a very limited time! Use our high-end AI tool to perfectly align your profile with the job requirements.
                                </p>
                            </div>

                            <!-- CTA Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 0 0 30px 0;">
                                <tr>
                                    <td align="center">
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                            <tr>
                                                <td align="center">
                                                    <a href="https://bhaikaamdo.com" style="display: inline-block; background-color: #667eea; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; padding: 16px 40px; border-radius: 6px; font-size: 16px; font-weight: 700; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);">
                                                        Avail This Chance Now
                                                    </a>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 20px 0; color: #333333; font-size: 16px; line-height: 1.6;">
                                This is your chance to stand out from the crowd. Don't let this opportunity slip away. Acting fast is the first step toward your new career.
                            </p>

                            <p style="margin: 0; color: #333333; font-size: 16px; line-height: 1.6;">
                                Thank you for being part of the <strong>Bhai Kaam Do</strong> community!
                            </p>
                        </td>
                    </tr>

                    <!-- Signature -->
                    <tr>
                        <td style="padding: 0 30px 40px 30px;">
                            <p style="margin: 0 0 5px 0; color: #333333; font-size: 16px; font-weight: 600;">
                                Best regards,
                            </p>
                            <p style="margin: 0; color: #667eea; font-size: 16px; font-weight: 600;">
                                The Bhai Kaam Do Team
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 30px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 14px;">
                                If you have any questions, feel free to reach out to us.
                            </p>
                            <p style="margin: 0; color: #6b7280; font-size: 14px; text-align: center;">
                                &copy; 2026 Bhai Kaam Do
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
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
    created_at: datetime

class AddCreditsRequest(BaseModel):
    user_email: EmailStr

class AddCreditsResponse(BaseModel):
    message: str
    new_credits: int

class NotificationRequest(BaseModel):
    user_email: str
    template_type: str  # "no_resume", "no_resume_with_jobs", "feedback", "fomo_promotion"

class UserDetailsResponse(BaseModel):
    processed_resumes: List[dict]
    processed_jobs: List[dict]
    improvements: List[dict]
    cover_letters: List[dict]

class DeleteRecordRequest(BaseModel):
    id: str

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
    users = await User.find({"$or": [{"local.token": {"$exists": True, "$ne": None}}, {"google.token": {"$exists": True, "$ne": None}}]}).to_list()
    
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
            
        # Priority for created_at: user.created_at -> user.verification_code.expires_at -> user.verification_attempts.last_attempt -> utcnow
        user_created_at = getattr(user, "created_at", None)
        if not user_created_at and user.verification_code:
            user_created_at = user.verification_code.expires_at
        if not user_created_at and user.verification_attempts:
            user_created_at = user.verification_attempts.last_attempt
        if not user_created_at:
            user_created_at = datetime.utcnow()

        all_stats.append(UserStats(
            user_email=email,
            processed_jobs_count=job_count,
            improvements_count=improvement_count,
            resumes_count=len(user_resumes),
            credits_remaining=user.credits_remaining,
            created_at=user_created_at
        ))
        
    # Sort by created_at in ascending order
    all_stats.sort(key=lambda x: x.created_at)
    
    return all_stats

@router.get("/details/{user_email}", response_model=UserDetailsResponse)
async def get_user_details(user_email: str, admin: User = Depends(get_admin_user)):
    # Find user by email in various auth fields
    user = await User.find_one({"local.email": user_email})
    if not user:
        user = await User.find_one({"google.email": user_email})
    if not user:
        user = await User.find_one({"facebook.email": user_email})
    if not user:
        user = await User.find_one({"linkedin.email": user_email})
        
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id_str = str(user.id)
    
    # Fetch all related records
    processed_jobs = await ProcessedJob.find(ProcessedJob.user_id == user_id_str).to_list()
    processed_resumes = await ProcessedResume.find(ProcessedResume.user_id == user_id_str).to_list()
    cover_letters = await CoverLetter.find(CoverLetter.user_id == user_id_str).to_list()
    
    # Improvements are linked to resumes, but let's fetch by user_id if possible, 
    # or follow the logic in get_all_users_stats
    resume_ids = [str(r.resume_id) for r in processed_resumes]
    # Also include base Resumes just in case
    base_resumes = await Resume.find(Resume.user_id == user_id_str).to_list()
    resume_ids.extend([str(r.resume_id) for r in base_resumes if str(r.resume_id) not in resume_ids])
    
    improvements = []
    if resume_ids:
        improvements = await Improvement.find(In(Improvement.resume_id, resume_ids)).to_list()
    
    # Convert Documents to dicts for JSON serialization using model_dump(mode='json', by_alias=True) to handle PydanticObjectId and _id alias
    return UserDetailsResponse(
        processed_resumes=[r.model_dump(mode='json', by_alias=True) for r in processed_resumes],
        processed_jobs=[j.model_dump(mode='json', by_alias=True) for j in processed_jobs],
        improvements=[i.model_dump(mode='json', by_alias=True) for i in improvements],
        cover_letters=[c.model_dump(mode='json', by_alias=True) for c in cover_letters]
    )

@router.delete("/delete-processed-job")
async def delete_processed_job(request: DeleteRecordRequest, admin: User = Depends(get_admin_user)):
    job = await ProcessedJob.get(request.id)
    if not job:
        raise HTTPException(status_code=404, detail="Processed Job not found")
    await job.delete()
    return {"message": "Processed Job deleted successfully"}

@router.delete("/delete-processed-resume")
async def delete_processed_resume(request: DeleteRecordRequest, admin: User = Depends(get_admin_user)):
    resume = await ProcessedResume.get(request.id)
    if not resume:
        raise HTTPException(status_code=404, detail="Processed Resume not found")
    await resume.delete()
    return {"message": "Processed Resume deleted successfully"}

@router.delete("/delete-improvement")
async def delete_improvement(request: DeleteRecordRequest, admin: User = Depends(get_admin_user)):
    improvement = await Improvement.get(request.id)
    if not improvement:
        raise HTTPException(status_code=404, detail="Improvement not found")
    await improvement.delete()
    return {"message": "Improvement deleted successfully"}

@router.delete("/delete-cover-letter")
async def delete_cover_letter(request: DeleteRecordRequest, admin: User = Depends(get_admin_user)):
    cl = await CoverLetter.get(request.id)
    if not cl:
        raise HTTPException(status_code=404, detail="Cover Letter not found")
    await cl.delete()
    return {"message": "Cover Letter deleted successfully"}

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
        subject = "Improve your job application success rate by 40%"
    else:
        raise HTTPException(status_code=400, detail="Invalid template type")
    
    send_notification_email(request.user_email, template, subject)
    return {"message": f"Notification '{request.template_type}' sent to {request.user_email}"}
