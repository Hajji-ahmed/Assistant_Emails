import smtplib
import ssl
import logging
import os
import sys
from email.mime.text import MIMEText
from email.utils import formataddr
from dotenv import load_dotenv


load_dotenv()


# Configuration
SENDER_EMAIL = os.getenv('GMAIL_USER') 
SENDER_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
RESUME_LINK = ""
DIRECT_DOWNLOAD = "https://drive.google.com/file/d/1gsVsdCpL4PToifUNp4F-AJnmUozZtedM/view?usp=drive_link"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def check_environment_variables():
    """Check that required environment variables are set"""
    if not SENDER_EMAIL:
        logger.error("GMAIL_USER environment variable not set")
        return False
    if not SENDER_PASSWORD:
        logger.error("GMAIL_APP_PASSWORD environment variable not set")
        return False
    return True

def create_test_email():
    """Create a test email with resume link verification"""
    subject = "Resume Link Test - Please Confirm Receipt"
    body = f"""Hello,

This is a test of my resume sending system. Please verify:

1. Resume View Link: {RESUME_LINK}
2. Direct Download: {DIRECT_DOWNLOAD}

Can you please:
1. Confirm you received this email
2. Verify both links work
3. Reply with "Links verified"

Thank you!
"""
    return create_email_message(
        recipient_name="Recipient",
        recipient_email="ahmdhajy301@gmail.com",
        subject=subject,
        body=body
    )

def create_email_message(recipient_name, recipient_email, subject, body):
    """Create properly formatted email message"""
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = formataddr(('Resume Sender', SENDER_EMAIL))
    msg['To'] = formataddr((recipient_name, recipient_email))
    return msg

def send_test_email():
    """Send verification email to personal address"""
    if not check_environment_variables():
        return False
        
    context = ssl.create_default_context()
    test_msg = create_test_email()
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(test_msg)
            logger.info("Test email sent successfully to 4bd3lm@gmail.com")
            logger.info(f"Resume links included:\nView: {RESUME_LINK}\nDownload: {DIRECT_DOWNLOAD}")
            return True
    except Exception as e:
        logger.error(f"Failed to send test email: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting resume link verification process")
    
    if send_test_email():
        logger.info("Please check your inbox at 4bd3lm@gmail.com")
        logger.info("Reply to confirm both the email and links work")
    else:
        logger.error("Test failed. Check your environment variables and Gmail SMTP settings")
        sys.exit(1)