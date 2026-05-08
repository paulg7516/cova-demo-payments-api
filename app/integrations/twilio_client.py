"""Twilio client for transactional SMS."""
import os

from twilio.rest import Client

_client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
FROM_NUMBER = os.environ["TWILIO_FROM_NUMBER"]


def send_sms(to: str, body: str) -> str:
    msg = _client.messages.create(from_=FROM_NUMBER, to=to, body=body)
    return msg.sid
