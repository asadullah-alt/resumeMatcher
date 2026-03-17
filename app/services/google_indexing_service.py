import json
import logging
import requests
import os
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from app.core.config import settings

logger = logging.getLogger(__name__)

class GoogleIndexingService:
    def __init__(self):
        self.credentials_path = settings.GOOGLE_INDEXING_CREDENTIALS_PATH
        self.scopes = ["https://www.googleapis.com/auth/indexing"]
        self.credentials = self._load_credentials()

    def _load_credentials(self):
        if not os.path.exists(self.credentials_path):
            logger.warning(f"Google Indexing credentials file not found at {self.credentials_path}")
            return None
        try:
            return service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=self.scopes
            )
        except Exception as e:
            logger.error(f"Failed to load Google Indexing credentials: {e}")
            return None

    def notify_job_added(self, job_id: str):
        """
        Sends a notification to Google about a new job.
        """
        job_url = f"{settings.FRONTEND_BASE_URL}/job/{job_id}"
        return self._send_notification(job_url, "URL_UPDATED")

    def _send_notification(self, url: str, action_type: str):
        if not self.credentials:
            logger.warning("Google Indexing credentials not available. Skipping notification.")
            return False

        endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
        
        try:
            authed_session = AuthorizedSession(self.credentials)
            payload = {
                "url": url,
                "type": action_type
            }
            
            response = authed_session.post(endpoint, json=payload)
            
            if response.status_code == 200:
                logger.info(f"✅ Google notified about: {url}")
                return True
            else:
                logger.error(f"❌ Google indexing notification failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"⚠️ Error notifying Google Indexing API: {e}")
            return False
