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
        parser.add_argument(
            "--skip-on-network-error",
            action="store_true",
            help="Exit successfully if the remote source cannot be fetched.",
        )

    def handle(self, *args, **options):
        source_defaults = self._load_source(
            options["source"],
            skip_on_network_error=options["skip_on_network_error"],
        )
        if source_defaults is None:
            self.stdout.write(
                self.style.WARNING(
                    "Skipped cookiecutter option coverage check because the remote source "
                    "is unavailable."
                )
            )
            return

        drift = diff_cookiecutter_defaults(source_defaults)

        if drift.has_drift:
            raise CommandError(drift.summary())

        self.stdout.write(self.style.SUCCESS("Cookiecutter options are covered by Djass."))

    def _load_source(
        self,
        source: str,
        *,
        skip_on_network_error: bool = False,
    ) -> OrderedDict | None:
        if source.startswith(("http://", "https://")):
            try:
                response = requests.get(source, timeout=20)
                response.raise_for_status()
            except requests.RequestException as exc:
                if skip_on_network_error and self._is_skippable_remote_error(exc):
                    return None
                raise CommandError(
                    f"Could not fetch remote cookiecutter options from {source}. "
                    f"This is a network or source availability failure: {exc}"
                ) from exc
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

    def _is_skippable_remote_error(self, exc: requests.RequestException) -> bool:
        if isinstance(exc, requests.HTTPError):
            status_code = exc.response.status_code if exc.response is not None else None
            return status_code is None or status_code >= 500
        return True
