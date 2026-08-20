"""
Thin wrapper around Meta's WhatsApp Cloud API for sending text replies.
Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"


def send_whatsapp_text(to_number: str, body: str) -> bool:
    """
    Sends a plain-text WhatsApp message to `to_number` (E.164 format,
    e.g. "923001234567" - no leading +).
    Returns True on success, False otherwise (and logs the error).
    """
    url = (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        # preview_url False avoids accidental link-preview cards
        "text": {"body": body, "preview_url": False},
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code >= 400:
            logger.error(
                "WhatsApp send failed (%s): %s", response.status_code, response.text
            )
            return False
        return True
    except requests.RequestException:
        logger.exception("WhatsApp send raised an exception")
        return False
