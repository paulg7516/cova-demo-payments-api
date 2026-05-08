"""SendGrid client for transactional email."""
import os

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

_client = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
FROM_ADDR = os.environ.get("SENDGRID_FROM", "no-reply@example.com")


def send_email(to: str, subject: str, html: str) -> int:
    msg = Mail(from_email=FROM_ADDR, to_emails=to, subject=subject, html_content=html)
    resp = _client.send(msg)
    return resp.status_code
