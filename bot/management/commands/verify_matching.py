"""
Run a battery of realistic rephrased questions against your loaded FAQ
data and report accuracy - use this after deploying somewhere with real
internet access (so the semantic model can download) to confirm it's
working, and to tune SEMANTIC_MATCH_THRESHOLD / AMBIGUITY_MARGIN in
matching.py if needed.

Usage:
    python manage.py verify_matching

Edit TEST_CASES below to use rephrasings of YOUR actual FAQ questions -
the ones here are just an example shape.
"""
from django.core.management.base import BaseCommand

from bot import semantic_matching
from bot.matching import resolve_match
from bot.models import QAPair

# Format: (rephrased question, expected exact question text from your doc, or None if it should NOT match anything)
TEST_CASES = [
    ("What does BVS stand for?", "What is BVS Stand for"),
    ("How do franchises get issued a BVS?", "What is the process of BVS Issuance"),
    ("What's the criteria to get a BVS device?", "What is the criteria of BVS Issuance"),
    ("Device is faulty, how do I get it fixed?", "What is the process of repairing if device is faulty"),
    ("Who can log into BMD portal?", "Who has access of BMD Portal"),
    ("Do I have to pay if my device breaks?", "Who will bear the cost of Device repairing"),
    ("Device can't be fixed, what next?", "If device is irreparable what is the further process"),
    ("How many days does a repair take?", "What is the TAT for repairing of device"),
    ("Where can I check my repair status?", "How franchise can check repairing status"),
    ("What are the different statuses shown in BMD?", "What are repairing status in BMD Portal"),
    ("What documents are needed to whitelist a device?", "What are requirements for Whitelisting of device"),
    ("Why would a BVS whitelist request get rejected?", "What are reason of BVS WL rejection"),
    ("TAT", "What is the TAT for repairing of device"),
    ("how do I report a stockout", None),
    ("what's the weather today", None),
]


class Command(BaseCommand):
    help = "Tests the matching algorithm against a battery of rephrased questions."

    def handle(self, *args, **options):
        self.stdout.write(f"Semantic matching available: {semantic_matching.semantic_available()}")

        if not TEST_CASES:
            self.stdout.write(self.style.WARNING(
                "TEST_CASES is empty - edit bot/management/commands/verify_matching.py "
                "and add rephrasings of your real FAQ questions before running this."
            ))
            return

        qa = QAPair.objects.all()
        if not qa.exists():
            self.stdout.write(self.style.ERROR("No Q&A pairs loaded - run load_qa first."))
            return

        correct = 0
        for question, expected in TEST_CASES:
            outcome = resolve_match(question, qa)
            if outcome.match:
                got = outcome.match.question
                ok = got == expected
                label = "OK" if ok else "WRONG"
                self.stdout.write(f"{label:6} score={outcome.match.score:5.1f}  {question!r} -> {got}")
            elif outcome.ambiguous_candidates:
                cands = [c.question for c in outcome.ambiguous_candidates]
                ok = expected in cands
                label = "AMBIG-OK" if ok else "AMBIG-WRONG"
                self.stdout.write(f"{label:12} {question!r} -> {cands}")
            else:
                ok = expected is None
                label = "OK" if ok else "NO-MATCH(WRONG)"
                self.stdout.write(f"{label:16} {question!r} (expected: {expected})")
            correct += ok

        self.stdout.write(self.style.SUCCESS(f"\n{correct}/{len(TEST_CASES)} correct"))
