from logging import LogRecord
from urllib.parse import urlparse

from sentry_sdk.integrations.logging import LoggingIntegration

_IGNORED_LOGGERS = {"ask_hn_digest"}
_HEALTHCHECK_PATHS = {"/api/healthcheck"}


class CustomLoggingIntegration(LoggingIntegration):
    def _handle_record(self, record: LogRecord) -> None:
        # This match upper logger names, e.g. "celery" will match "celery.worker"
        # or "celery.worker.job"
        if record.name in _IGNORED_LOGGERS or record.name.split(".")[0] in _IGNORED_LOGGERS:
            return
        super()._handle_record(record)


def before_send(event, hint):
    if "exc_info" in hint:
        _exc_type, exc_value, _tb = hint["exc_info"]

        if isinstance(exc_value, SystemExit):  # group all SystemExits together
            event["fingerprint"] = ["system-exit"]
    return event


def before_send_transaction(event, hint):
    """Drop noisy healthcheck transactions before they leave the app."""

    request = event.get("request") or {}
    url = request.get("url")
    if url and urlparse(url).path in _HEALTHCHECK_PATHS:
        return None

    transaction = event.get("transaction") or ""
    if transaction in _HEALTHCHECK_PATHS:
        return None

    return event
