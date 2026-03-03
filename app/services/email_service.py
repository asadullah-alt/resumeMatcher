import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import email.utils

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.email_user = os.getenv('EMAIL_USER', 'support@bhaikaamdo.com')
        self.email_password = os.getenv('EMAIL_PASSWORD', 'Apogee12345!')
        self.smtp_server = 'mail-eu.smtp2go.com'
        self.smtp_port = 2525

    def send_email(self, to_email: str, subject: str, template_html: str):
        """Sends an HTML email with improved deliverability headers."""
        msg = MIMEMultipart()
        
        # Standard Headers
        msg['From'] = f"Bhai Kaam Do Support <{self.email_user}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg['Date'] = email.utils.formatdate(localtime=True)
        msg['Message-ID'] = email.utils.make_msgid(domain='bhaikaamdo.com')
        
        # Deliverability/Spam Prevention Headers
        msg['List-Unsubscribe'] = f"<mailto:support@bhaikaamdo.com?subject=Unsubscribe%20{to_email}>"
        msg['Precedence'] = 'bulk'
        msg['X-Auto-Response-Suppress'] = 'All'
        
        msg.attach(MIMEText(template_html, 'html'))
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)
            logger.info(f"Successfully sent email to {to_email} with subject: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
