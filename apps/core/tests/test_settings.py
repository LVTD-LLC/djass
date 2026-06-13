import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]


def _load_secure_proxy_ssl_header(environment: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": "sqlite:///tmp/settings-test.sqlite3",
            "DEBUG": "False",
            "ENVIRONMENT": environment,
            "SECRET_KEY": "test-secret-key",
            "SITE_URL": "https://djass.dev" if environment == "prod" else "http://localhost",
        }
    )
    env.pop("DJANGO_SETTINGS_MODULE", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import djass.settings as settings; "
                "print(repr(getattr(settings, 'SECURE_PROXY_SSL_HEADER', None)))"
            ),
        ],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def test_secure_proxy_ssl_header_is_disabled_outside_prod():
    assert _load_secure_proxy_ssl_header("dev") == "None"


def test_secure_proxy_ssl_header_is_enabled_in_prod():
    assert _load_secure_proxy_ssl_header("prod") == "('HTTP_X_FORWARDED_PROTO', 'https')"
