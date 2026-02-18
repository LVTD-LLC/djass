import structlog


def get_djass_logger(name):
    """This will add a `djass` prefix to logger for easy configuration."""

    return structlog.get_logger(
        f"djass.{name}",
        project="djass"
    )
