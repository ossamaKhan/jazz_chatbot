"""
Detects casual small-talk (greetings) so they get a friendly canned reply
instead of being run through FAQ matching, where they'd correctly find
no match (since "hi" isn't a real franchise-ops question) but that reads
as a broken/unhelpful bot to a real user's first message.

Kept deliberately narrow: only common greeting words/phrases, checked as
the WHOLE message (short) - so "hi, how do I report a stockout" still
goes to normal FAQ matching rather than being swallowed as small talk.
"""
import re
import string

ASSISTANT_NAME = "SmartAssist"

GREETING_WORDS = {
    "hi", "hii", "hiii", "hey", "heyy", "hello", "helo", "yo",
    "hi there", "hello there", "hey there",
    "salam", "assalam", "assalamualaikum", "assalamoalaikum",
    "good morning", "good afternoon", "good evening",
    "how are you", "whats up", "what's up",
}

GREETING_REPLY = (
    f"Hi, I am {ASSISTANT_NAME}. Please ask me questions related to "
    "franchise operations, BVS devices, credit, DFS agents, and more."
)


def _normalize(text: str) -> str:
    stripped = text.strip().lower()
    stripped = stripped.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", stripped).strip()


def is_greeting(user_text: str) -> bool:
    normalized = _normalize(user_text)
    if not normalized:
        return False
    # Only treat as small talk if the ENTIRE (short) message is just a
    # greeting - not a real question that happens to start with "hi".
    if len(normalized.split()) > 4:
        return False
    return normalized in GREETING_WORDS