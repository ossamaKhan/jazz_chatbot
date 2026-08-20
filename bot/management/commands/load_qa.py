from django.core.management.base import BaseCommand, CommandError

from bot.docx_loader import parse_qa_docx
from bot.models import QAPair


class Command(BaseCommand):
    help = "Loads Q&A pairs from a Word document into the database."

    def add_arguments(self, parser):
        parser.add_argument("docx_path", type=str, help="Path to the .docx file")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete all existing QAPair rows before loading (clean reload).",
        )

    def handle(self, *args, **options):
        path = options["docx_path"]
        replace = options["replace"]

        try:
            pairs = parse_qa_docx(path)
        except FileNotFoundError:
            raise CommandError(f"File not found: {path}")
        except ValueError as exc:
            raise CommandError(str(exc))

        if replace:
            deleted, _ = QAPair.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing Q&A pairs.")

        created = 0
        for question, answer in pairs:
            QAPair.objects.create(
                question=question,
                answer=answer,
                question_normalized=" ".join(question.lower().split()),
                source_doc=path,
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(f"Loaded {created} Q&A pairs from {path}.")
        )
