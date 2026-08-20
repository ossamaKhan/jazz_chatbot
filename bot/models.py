from django.db import models


class QAPair(models.Model):
    """A single question/answer pair loaded from the Word document."""

    question = models.TextField()
    answer = models.TextField()
    # Normalized version of the question, cached for faster matching.
    question_normalized = models.TextField(db_index=True)
    source_doc = models.CharField(max_length=255, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.question[:60]


class IncomingMessageLog(models.Model):
    """Log of who asked what, and whether we found an answer.
    Useful for spotting questions people ask that aren't in the doc yet.
    """

    from_number = models.CharField(max_length=32)
    message_text = models.TextField()
    matched_question = models.TextField(blank=True, null=True)
    match_score = models.FloatField(blank=True, null=True)
    answered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
