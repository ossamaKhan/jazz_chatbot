# FAQ Bot - Web Chat + WhatsApp

Answers questions using Q&A pairs pulled from a Word document. No AI
involved - matching is done with fuzzy string comparison (rapidfuzz),
so it's fast, free, and fully under your control.

Two front doors, same backend and same Word doc:
- **Web chat widget** at `/` - no external accounts, no approval process, works immediately.
- **WhatsApp** at `/bot/webhook/` - via Meta's official Cloud API (see WhatsApp section below).

## Quick start (web chat only)

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py load_qa /path/to/your/faq.docx --replace
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in a browser - that's it, no ngrok, no
Meta app, no webhook setup needed. Re-run `load_qa --replace` any time
the Word doc changes.

### How matching works, and its real limits

Matching has two layers, used automatically depending on what's available:

**1. Semantic matching (preferred)** - uses a `sentence-transformers`
model (`all-MiniLM-L6-v2`) that understands *meaning*, not just words.
This is what lets a true synonym swap match correctly - e.g. "who will
**pay** for repairs" against your doc's "who will **bear the cost** of
repairs" - something word-overlap methods cannot reliably solve, no
matter how they're tuned (verified through extensive testing while
building this).

This is a **local model**, not a hosted AI API like Gemini/OpenAI - it
downloads once (~90MB) the first time it runs, then works entirely
offline with no per-message cost and nothing sent externally.

**Requirements:**
- Internet access the *first* time the app starts (to download the
  model from huggingface.co) - after that it's cached and works offline.
- Noticeably more RAM than the lightweight fallback below - likely too
  much for Render's free tier. A paid tier, or a host with more memory,
  is probably needed for this layer to actually run in production.

**2. Word-overlap fallback (always available)** - if the semantic model
isn't installed, or can't load (no internet on first run, insufficient
memory, etc.), the bot automatically and silently falls back to a
TF-IDF + fuzzy-matching hybrid that needs no extra dependencies. Your
bot keeps working either way - this is a safety net, not an error state.

### Verifying and tuning semantic matching

The threshold used when semantic matching is active
(`SEMANTIC_MATCH_THRESHOLD` in `bot/matching.py`) is a reasonable
starting point, but couldn't be empirically tuned in the environment
this was built in (no internet access to the model host there). Once
you're running somewhere with real internet access:

```bash
python manage.py verify_matching
```

This runs a battery of rephrased BVS questions and reports accuracy. If
real matches are consistently landing just above/below the threshold,
adjust `SEMANTIC_MATCH_THRESHOLD` in `bot/matching.py` accordingly. Edit
the `TEST_CASES` list in `bot/management/commands/verify_matching.py`
to test rephrasings specific to your actual FAQ content as it grows.

## Deploying (e.g. Render, same as your other projects)

- Build command: `pip install -r requirements.txt`
- Start command: `python manage.py migrate && gunicorn faqbot.wsgi`
- Set env vars from `.env.example` in Render's dashboard.
- Re-run `load_qa` (via Render's shell) whenever the FAQ doc changes.
- The web chat works immediately at your Render URL. WhatsApp needs
  the additional Meta setup below, and the Callback URL updated to
  your Render domain instead of ngrok.

---

# WhatsApp setup (optional)

Uses Meta's official WhatsApp Cloud API directly (no third-party BSP
needed). Replies to customer-initiated messages are free under Meta's
"service conversation" category.

---

## 1. Prepare your Word document

Easiest format - a table with two columns:

| Question               | Answer                              |
|-------------------------|--------------------------------------|
| What is a BVS device?   | BVS stands for ...                  |
| What does ARM mean?     | ARM refers to ...                   |

The first row can be a header ("Question"/"Answer") - it's auto-detected
and skipped. You can also use plain paragraphs instead of a table:

```
Q: What is a BVS device?
A: BVS stands for ...

Q: What does ARM mean?
A: ARM refers to ...
```

Multiple tables/pairs in one doc are all picked up.

## 2. Local setup

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env           # then fill in the WhatsApp values (step 4)

python manage.py migrate
python manage.py createsuperuser   # so you can view logs at /admin/

# Load your Q&A doc into the database:
python manage.py load_qa /path/to/your/faq.docx --replace
```

`--replace` wipes existing Q&A pairs first, so re-running this after
editing the Word doc keeps things in sync. Re-run it any time the doc
changes.

## 3. Run it locally and expose it

```bash
python manage.py runserver
```

Meta needs a public HTTPS URL to send webhooks to. For local testing,
use ngrok:

```bash
ngrok http 8000
```

Note the `https://xxxx.ngrok-free.app` URL it gives you - your webhook
URL will be `https://xxxx.ngrok-free.app/bot/webhook/`.

## 4. Set up the Meta WhatsApp app (one-time)

1. Go to https://developers.facebook.com/apps and create an app ->
   choose "Business" type -> add the **WhatsApp** product.
2. Under **WhatsApp > API Setup** you'll see:
   - A **temporary access token** (valid 24h, fine for testing) and a
     **test phone number** you can message from your own WhatsApp.
   - A **Phone number ID** - copy this into `.env` as
     `WHATSAPP_PHONE_NUMBER_ID`.
   - Copy the access token into `.env` as `WHATSAPP_ACCESS_TOKEN`.
3. Pick any secret string yourself for `WHATSAPP_VERIFY_TOKEN` in
   `.env` - you'll type this same value into Meta's dashboard next.
4. In **WhatsApp > Configuration**, click **Edit** on Webhook and enter:
   - Callback URL: `https://xxxx.ngrok-free.app/bot/webhook/`
   - Verify token: the same string you put in `.env`
   - Subscribe to the **messages** field.
5. Message the test number from your phone and watch it reply.

For production (a real business number instead of the test number),
you'll need to add a phone number, verify your business, and switch
from the temporary token to a permanent one under **System Users** -
Meta's dashboard walks you through this.

## 5. Deploy (e.g. on Render, same as your other projects)

- Build command: `pip install -r requirements.txt`
- Start command: `python manage.py migrate && gunicorn faqbot.wsgi`
- Set the same env vars from `.env` in Render's dashboard
  (`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` = your Render domain,
  `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
  `WHATSAPP_VERIFY_TOKEN`).
- Update the webhook Callback URL in the Meta Dashboard to your Render
  URL once deployed (`https://your-app.onrender.com/bot/webhook/`).
- Re-run `load_qa` against the deployed database whenever the FAQ doc
  changes (e.g. via Render's shell, or a small management endpoint).

## 6. Tuning the matching

In `bot/matching.py`, `MATCH_THRESHOLD` (default 65, scale 0-100)
controls how close a message must be to a stored question before it's
treated as a match. Lower it if legitimate questions are getting
"couldn't find an answer" too often; raise it if it's answering
unrelated questions incorrectly.

## 7. Checking what people are asking

Every incoming message is logged in `IncomingMessageLog`
(visible at `/admin/`), including whether it was answered and the
match confidence score. Good source for spotting questions to add to
the Word doc.
