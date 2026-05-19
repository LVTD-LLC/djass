import json
from collections import OrderedDict
from pathlib import Path

import requests
from django.core.management.base import BaseCommand, CommandError

from apps.core.generator_options import (
    COOKIECUTTER_OPTIONS_SOURCE_URL,
    diff_cookiecutter_defaults,
)


class Command(BaseCommand):
    help = "Check Djass generator option coverage against django-saas-starter cookiecutter.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=COOKIECUTTER_OPTIONS_SOURCE_URL,
            help="cookiecutter.json URL or local file path.",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Compatibility flag; this command always checks and never writes.",
        )

    def handle(self, *args, **options):
        source_defaults = self._load_source(options["source"])
        drift = diff_cookiecutter_defaults(source_defaults)

        if drift.has_drift:
            raise CommandError(drift.summary())

        self.stdout.write(self.style.SUCCESS("Cookiecutter options are covered by Djass."))

    def _load_source(self, source: str) -> OrderedDict:
        if source.startswith(("http://", "https://")):
            try:
                response = requests.get(source, timeout=20)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise CommandError(f"Could not fetch cookiecutter options: {exc}") from exc
            raw_content = response.text
        else:
            try:
                raw_content = Path(source).read_text(encoding="utf-8")
            except OSError as exc:
                raise CommandError(f"Could not read cookiecutter options: {exc}") from exc

        try:
            loaded = json.loads(raw_content, object_pairs_hook=OrderedDict)
        except json.JSONDecodeError as exc:
            raise CommandError(f"Source is not valid JSON: {exc}") from exc

        if not isinstance(loaded, OrderedDict):
            raise CommandError("Source must be a JSON object.")
        return loaded
