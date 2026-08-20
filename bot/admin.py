from django.contrib import admin

from .models import IncomingMessageLog, QAPair


@admin.register(QAPair)
class QAPairAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "source_doc", "updated_at")
    search_fields = ("question", "answer")


@admin.register(IncomingMessageLog)
class IncomingMessageLogAdmin(admin.ModelAdmin):
    list_display = ("from_number", "message_text", "matched_question", "match_score", "answered", "created_at")
    list_filter = ("answered",)
    search_fields = ("from_number", "message_text")
    readonly_fields = [f.name for f in IncomingMessageLog._meta.fields]
