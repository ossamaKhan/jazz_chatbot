import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .matching import resolve_match
from .models import IncomingMessageLog, QAPair
from .smalltalk import GREETING_REPLY, is_greeting
from .whatsapp import send_whatsapp_text

logger = logging.getLogger(__name__)

NOT_FOUND_REPLY = (
    "I couldn't find an answer to that in my records. "
    "Try rephrasing, or someone from the team will follow up."
)


def _build_ambiguous_reply(candidates) -> str:
    options = "\n".join(f"- {c.question}" for c in candidates)
    return (
        "That could match a few different things - could you be more specific?\n"
        f"{options}"
    )


def chat_page(request):
    """Renders the web chat widget."""
    return render(request, "bot/chat.html")


@csrf_exempt
def ask(request):
    """
    JSON endpoint for the web chat widget.
    POST {"message": "what is a bvs device"}
    -> {"answer": "...", "matched": true, "score": 98.7, "ambiguous": false}
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    user_text = (body.get("message") or "").strip()
    if not user_text:
        return JsonResponse({"error": "message is required"}, status=400)

    qa_pairs = QAPair.objects.all()

    if is_greeting(user_text):
        IncomingMessageLog.objects.create(
            from_number="web",
            message_text=user_text,
            matched_question=None,
            match_score=None,
            answered=True,
        )
        return JsonResponse(
            {
                "answer": GREETING_REPLY,
                "matched": False,
                "score": None,
                "matched_question": None,
                "ambiguous": False,
                "greeting": True,
            }
        )

    outcome = resolve_match(user_text, qa_pairs)

    if outcome.match:
        answer_text = outcome.match.answer
        matched = True
        score = round(outcome.match.score, 1)
        matched_question = outcome.match.question
        ambiguous = False
    elif outcome.ambiguous_candidates:
        answer_text = _build_ambiguous_reply(outcome.ambiguous_candidates)
        matched = False
        score = None
        matched_question = None
        ambiguous = True
    else:
        answer_text = NOT_FOUND_REPLY
        matched = False
        score = None
        matched_question = None
        ambiguous = False

    IncomingMessageLog.objects.create(
        from_number="web",
        message_text=user_text,
        matched_question=matched_question,
        match_score=score,
        answered=matched,
    )

    return JsonResponse(
        {
            "answer": answer_text,
            "matched": matched,
            "score": score,
            "matched_question": matched_question,
            "ambiguous": ambiguous,
            "greeting": False,
        }
    )


@csrf_exempt
def webhook(request):
    if request.method == "GET":
        return _handle_verification(request)
    if request.method == "POST":
        return _handle_incoming(request)
    return HttpResponse(status=405)


def _handle_verification(request):
    """
    Meta calls this once, when you set up the webhook in the App
    Dashboard, to prove you control this URL.
    """
    mode = request.GET.get("hub.mode")
    token = request.GET.get("hub.verify_token")
    challenge = request.GET.get("hub.challenge")

    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        return HttpResponse(challenge)
    return HttpResponseForbidden("Verification failed")


def _handle_incoming(request):
    """
    Handles the payload Meta POSTs whenever a message arrives.
    Structure: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        logger.warning("Received non-JSON webhook body")
        return JsonResponse({"status": "ignored"}, status=200)

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                _process_message(message)

    # Always 200 quickly - Meta retries aggressively on non-200s.
    return JsonResponse({"status": "received"}, status=200)


def _process_message(message: dict):
    if message.get("type") != "text":
        # Only handling plain text for now; could extend to button/list replies.
        return

    from_number = message.get("from")
    user_text = message.get("text", {}).get("body", "").strip()
    if not from_number or not user_text:
        return

    qa_pairs = QAPair.objects.all()

    if is_greeting(user_text):
        send_whatsapp_text(from_number, GREETING_REPLY)
        IncomingMessageLog.objects.create(
            from_number=from_number,
            message_text=user_text,
            matched_question=None,
            match_score=None,
            answered=True,
        )
        return

    outcome = resolve_match(user_text, qa_pairs)

    if outcome.match:
        reply_text = outcome.match.answer
        matched_question = outcome.match.question
        score = outcome.match.score
        answered = True
    elif outcome.ambiguous_candidates:
        reply_text = _build_ambiguous_reply(outcome.ambiguous_candidates)
        matched_question = None
        score = None
        answered = False
    else:
        reply_text = NOT_FOUND_REPLY
        matched_question = None
        score = None
        answered = False

    send_whatsapp_text(from_number, reply_text)

    IncomingMessageLog.objects.create(
        from_number=from_number,
        message_text=user_text,
        matched_question=matched_question,
        match_score=score,
        answered=answered,
    )