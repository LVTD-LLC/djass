import json
from collections import OrderedDict
from pathlib import Path

import requests
from django.core.management.base import BaseCommand, CommandError

from apps.core.generator_options import (
    COOKIECUTTER_FIELD_DEFAULTS,
    COOKIECUTTER_OPTIONS_PATH,
    COOKIECUTTER_OPTIONS_SOURCE_URL,
    serialize_cookiecutter_defaults,
)


class Command(BaseCommand):
    help = "Compare or update Djass generator options from django-saas-starter cookiecutter.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=COOKIECUTTER_OPTIONS_SOURCE_URL,
            help="cookiecutter.json URL or local file path.",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Fail if the checked-in option snapshot differs from the source.",
        )
        parser.add_argument(
            "--write",
            action="store_true",
            help="Overwrite the checked-in option snapshot from the source.",
        )

    def handle(self, *args, **options):
        if options["check"] and options["write"]:
            raise CommandError("Use either --check or --write, not both.")

        source = options["source"]
        source_defaults = self._load_source(source)
        local_defaults = COOKIECUTTER_FIELD_DEFAULTS

        if source_defaults == local_defaults:
            self.stdout.write(self.style.SUCCESS("Cookiecutter options are up to date."))
            return

        summary = self._drift_summary(local_defaults, source_defaults)
        if options["check"]:
            raise CommandError(summary)

        if options["write"]:
            COOKIECUTTER_OPTIONS_PATH.write_text(
                serialize_cookiecutter_defaults(source_defaults),
                encoding="utf-8",
            )
            self.stdout.write(self.style.SUCCESS("Cookiecutter options updated."))
            self.stdout.write(str(COOKIECUTTER_OPTIONS_PATH))
            return

        self.stdout.write(summary)
        self.stdout.write("Run again with --write to update the checked-in snapshot.")

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

    def _drift_summary(self, local_defaults: OrderedDict, source_defaults: OrderedDict) -> str:
        local_keys = set(local_defaults)
        source_keys = set(source_defaults)
        added = sorted(source_keys - local_keys)
        removed = sorted(local_keys - source_keys)
        changed = sorted(
            key
            for key in local_keys & source_keys
            if local_defaults[key] != source_defaults[key]
        )

        details = ["Cookiecutter option snapshot is out of date."]
        if added:
            details.append(f"Added upstream: {', '.join(added)}")
        if removed:
            details.append(f"Removed upstream: {', '.join(removed)}")
        if changed:
            details.append(f"Changed defaults: {', '.join(changed)}")
        return "\n".join(details)
