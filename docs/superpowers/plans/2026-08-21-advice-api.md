# Advice API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve an explainable advice over HTTP from four answers, without an account, and let the visitor come back to it later through a shareable link.

**Architecture:** A Django project in `backend/` that imports the two pure packages and never the other way round. The request path is synchronous: validate, assemble domain objects, run the engine, render, store, audit. Every source of external data enters through the provider protocols that already exist, so the API adds a cache and a boundary and no second engine.

**Tech Stack:** Django 5.2 LTS, Django REST Framework 3.18, PostgreSQL 16 via psycopg 3, pytest-django, uv.

**Spec:** `docs/superpowers/specs/2026-08-21-advice-api-design.md`

## Global Constraints

- `ampeer_sim` and `ampeer_advice` must not import Django, and must not import `backend`. Enforced by `tests/test_boundaries.py`.
- No Dutch text anywhere outside `ampeer_advice/nl.py`. The API renders text by rule id; it never writes a sentence.
- Money is `Decimal`, energy is `float`. Money crosses the HTTP boundary as a **string**, quantized in exactly one function.
- Every response carries a band. There is no field anywhere that holds `p50` alone.
- `confidence` sits at the top level of the response, never nested.
- The three routes are always emitted, always in the same order, free routes first, even when empty.
- Coverage floor stays at 98 or higher and `precision = 2` stays. `backend` joins `[tool.coverage.run] source` in Task 1, so from that moment on every line written here is measured.
- `mypy --strict` must pass over `ampeer_sim`, `ampeer_advice`, `tools` **and** `backend`.
- Work on `feat/advice-api`. Never commit directly to `main`.

### Pinned versions, and why these

| Package | Version | Reason |
|---|---|---|
| Django | `>=5.2.17,<6.0` | 5.2 is LTS with security support to April 2028. Django 6.1 is current but non-LTS: its support window closes around April 2027, which is the quarter net metering ends and this product is at its busiest. Choosing 6.1 would schedule a forced major upgrade for the worst possible month. `CLAUDE.md` also says Django 5. Next planned move is 6.2 LTS when it lands. |
| djangorestframework | `>=3.18.0` | Current release, supports Django 5.2. |
| psycopg[binary] | `>=3.3.4` | Django 5.2's recommended Postgres driver. `psycopg2` is legacy. |
| pytest-django | `>=4.14.0` | Requires Django >= 5.2, which we have. |
| django-stubs[compatible-mypy] | `>=6.1.0` | Without it `mypy --strict` cannot see through the ORM and every model attribute becomes `Any`, which turns strict mode into decoration. |
| djangorestframework-stubs | `>=3.18.0` | Same reason for the DRF half. |
| `postgres:16-alpine` | `@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685` | Resolved from Docker Hub on 2026-08-21. Tags are mutable; the pipeline already refuses unpinned `uses:` and a service container image is the same exposure. |

---

## The multi-agent working model

The five rules that make concurrency safe, carried over from the two plans that ran before this one:

1. **A lane owns paths exclusively.** No two lanes write the same file.
2. **Implementation agents never run git.** The integration gate commits.
3. **Every lane runs its own verification command** and reports the output.
4. **Gates run after lanes.** Integration first, audit second.
5. **A lane may not run a tool that writes outside the files it owns.** Formatters, code generators and `pre-commit run --all-files` belong in the barrier, never in a lane. Lanes verify with `uv run --no-sync <tool>` against their own paths only.

A sixth rule, learned when a lane in the previous plan could not import its own package because the plan named the coverage source but not the packaging include:

6. **A lane that finds it cannot proceed without editing a file it does not own stops and reports.** It does not reach across the line. The barrier fixes it centrally and the plan gets corrected.

### File ownership map

| Lane | Owns exclusively |
|---|---|
| **0. Foundation** | `pyproject.toml`, `backend/manage.py`, `backend/ampeer/**`, `backend/advice/__init__.py`, `backend/advice/apps.py`, `tests/conftest.py`, `tests/test_backend_settings.py`, `tests/test_boundaries.py`, `tests/test_pipeline_contract.py`, `.github/workflows/ci.yml` |
| **A. Storage** | `backend/advice/models.py`, `backend/advice/migrations/**`, `backend/advice/management/**`, `tests/test_advice_models.py` |
| **B. Input** | `backend/advice/serializers.py`, `tests/test_advice_serializers.py` |
| **C. Providers** | `backend/advice/production.py`, `backend/advice/profiles.py`, `tests/test_advice_providers.py` |
| **D. Assembly and rendering** | `backend/advice/assembly.py`, `backend/advice/rendering.py`, `tests/test_advice_assembly.py`, `tests/test_advice_rendering.py` |
| **Integration** | `backend/advice/service.py`, `backend/advice/views.py`, `backend/advice/urls.py`, `tests/test_advice_api.py`, and a single re-edit of `backend/ampeer/urls.py` |

`backend/ampeer/urls.py` is the one shared file. Foundation creates it with an empty
`urlpatterns`; integration adds the one `include`. They never run at the same time, so
this is safe, but no lane may touch it.

### File structure

```
backend/
  manage.py                     entry point, no logic, omitted from coverage
  ampeer/
    settings/base.py            everything shared
    settings/dev.py             DEBUG allowed here and nowhere else
    settings/prod.py            refuses to start without its secrets
    settings/test.py            LocMemCache, real Postgres
    urls.py                     mounts /api/advice/
    wsgi.py                     entry point, omitted from coverage
  advice/
    models.py        (A)  StoredAdvice, AuditEvent, ProductionCache
    migrations/      (A)
    management/commands/purge_expired_advice.py  (A)
    serializers.py   (B)  the only place untrusted input is shaped
    production.py    (C)  CachedProductionProvider
    profiles.py      (C)  which ProfileProvider this deployment uses
    assembly.py      (D)  validated data -> Household, PVSystem, TariffSet
    rendering.py     (D)  Advice + Result -> JSON-safe dict
    service.py       (I)  the composition root
    views.py         (I)  three endpoints, throttle scopes
    urls.py          (I)
```

The split is by responsibility and not by Django convention. `serializers.py` holds
input only and `rendering.py` output only, because they fail differently: a validation
bug lets bad data in, a rendering bug shows a wrong number to a reader. Keeping them
apart means one test file can be about trust and the other about honesty.

---

## Two things this plan settles that the spec left implicit

**`filled_fields` counts answered questions, not serializer fields.** `ampeer_advice.confidence` calls an
advice GOOD from `GOOD_FIELD_COUNT = 5` upward. Round 1 asks four questions but yields
five values, because orientation and tilt are one question about one roof. Passing the
value count would make every estimate GOOD and quietly delete the distinction the whole
confidence label exists for. Round 1 therefore passes `4` and round 2 passes `9`.
Task 6 pins this with a test on both endpoints, because nothing else would notice it
drifting.

**Azimuth and tilt are rounded to whole degrees on the way in, once.** A float in a cache
key means `35.000000001` misses a cache entry made for `35.0`, and worse, a cache hit on
a rounded key would hand back a series computed for a slightly different roof than the
simulation then assumes. Rounding in the serializer makes one value flow everywhere:
into the cache key, into the PVGIS call and into `PVSystem`. Nobody knows their roof
angle to better than a degree, so nothing is lost.

---

## Phase 0: foundation

### Task 1: The Django project, its settings, and the gates that must cover it

**Files:**
- Modify: `pyproject.toml`
- Create: `backend/manage.py`, `backend/ampeer/__init__.py`, `backend/ampeer/settings/__init__.py`, `backend/ampeer/settings/base.py`, `backend/ampeer/settings/dev.py`, `backend/ampeer/settings/prod.py`, `backend/ampeer/settings/test.py`, `backend/ampeer/urls.py`, `backend/ampeer/wsgi.py`, `backend/advice/__init__.py`, `backend/advice/apps.py`, `tests/conftest.py`, `tests/test_backend_settings.py`
- Modify: `tests/test_boundaries.py`, `tests/test_pipeline_contract.py`, `.github/workflows/ci.yml`

**Interfaces:**
- Produces: settings module `ampeer.settings.test` importable with `backend/` on `sys.path`; Django app label `advice`; setting `AMPEER_NEDU_PROFILE_PATH: str | None`; setting `AMPEER_WEATHER_YEAR: int`; setting `AMPEER_PROFILE_YEAR: int`; DRF throttle scopes `advice-compute` and `advice-read`.
- Consumes: nothing.

- [ ] **Step 1: Add the backend dependency group and put `backend` under the gates**

In `pyproject.toml`, add a new group and extend three existing tables. Nothing else in
the file changes.

```toml
[dependency-groups]
backend = [
    "django>=5.2.17,<6.0",
    "djangorestframework>=3.18.0",
    "psycopg[binary]>=3.3.4",
]
dev = [
    # ... existing entries stay exactly as they are, add these four:
    "pytest-django>=4.14.0",
    "django-stubs[compatible-mypy]>=6.1.0",
    "djangorestframework-stubs>=3.18.0",
]
```

```toml
[tool.setuptools.packages.find]
include = ["ampeer_sim*", "ampeer_advice*", "tools*"]
# backend/ is deliberately absent. It is a Django project run from its own
# directory, not a library anybody installs, and adding it here would put a
# module named `ampeer` on the path that shadows nothing useful.
```

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["backend"]
DJANGO_SETTINGS_MODULE = "ampeer.settings.test"
filterwarnings = ["ignore::DeprecationWarning:pytest_asyncio.*"]
```

```toml
[tool.coverage.run]
source = ["ampeer_sim", "ampeer_advice", "tools", "backend"]
# Two entry points and nothing else. Django generates both, neither holds a
# decision, and neither is imported by a test. Every other line under backend/
# is measured. This list is asserted to stay exactly this short by
# tests/test_pipeline_contract.py, because an omit list is the quietest way to
# make a coverage floor stop meaning anything.
omit = ["backend/manage.py", "backend/ampeer/wsgi.py"]
```

```toml
[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["mypy_django_plugin.main", "mypy_drf_plugin.main"]
mypy_path = "backend"

[tool.django-stubs]
django_settings_module = "ampeer.settings.test"
```

Run `uv lock` and `uv sync --locked --group dev --group backend`.

- [ ] **Step 2: Write the settings, split three ways**

`backend/ampeer/settings/base.py`:

```python
"""Settings shared by every environment.

Nothing here reads an environment variable that decides a security property.
Those live in prod.py, where a missing value stops the process instead of
falling back to something permissive.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "advice.apps.AdviceConfig",
]

# No auth, no sessions, no admin. There is nothing to log in to in this phase,
# and an installed app is an attack surface whether or not a URL points at it.

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ampeer.urls"
WSGI_APPLICATION = "ampeer.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Stored in UTC, shown in Europe/Amsterdam. The engine works on a grid in
# continuous winter time and never sees a Django timestamp, so this setting
# governs the audit log and nothing in the model.
TIME_ZONE = "UTC"
USE_TZ = True
LANGUAGE_CODE = "nl-nl"

STATIC_URL = "static/"

REST_FRAMEWORK = {
    # Anonymous by design. There is no account to authenticate.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        # A computation costs about half a second of CPU. Twenty an hour is
        # generous for a real visit and far too little to occupy the machine.
        "advice-compute": "20/hour",
        # Opening and sharing a link must not require thinking about it.
        "advice-read": "120/hour",
    },
    "UNAUTHENTICATED_USER": None,
}

#: The NEDU standard profile file. There is no default and there is no
#: fallback shape: a consumption profile that nobody measured would be an
#: invented number at the centre of every answer. prod.py refuses to start
#: without it. See profiles.py.
AMPEER_NEDU_PROFILE_PATH: str | None = os.environ.get("AMPEER_NEDU_PROFILE_PATH")

#: The weather year and profile year every request is computed for. Both are
#: closed years, so an advice is reproducible from its stored inputs.
AMPEER_WEATHER_YEAR = 2023
AMPEER_PROFILE_YEAR = 2025

#: How long a stored advice stays retrievable.
AMPEER_ADVICE_TTL_DAYS = 90
```

`backend/ampeer/settings/dev.py`:

```python
"""Developer machine. The only file in which DEBUG may be true."""

from __future__ import annotations

import os

from ampeer.settings.base import *  # noqa: F403

DEBUG = True
SECRET_KEY = "dev-only-not-a-secret"  # noqa: S105
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "ampeer"),
        "USER": os.environ.get("POSTGRES_USER", "ampeer"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "ampeer"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}
```

`backend/ampeer/settings/test.py`:

```python
"""The test environment. Postgres, because the schema under test must be the
schema that ships. An in-memory SQLite would hide a whole class of fault, and
this project exists to have no invisible failure modes."""

from __future__ import annotations

from ampeer.settings.dev import *  # noqa: F403

DEBUG = False

# Throttling is live in tests. A separate local cache keeps one test's requests
# out of another's counter; tests/conftest.py clears it before each test.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "ampeer-tests",
    }
}
```

`backend/ampeer/settings/prod.py`:

```python
"""Production. Every value that decides a security property comes from the
environment and has no default.

A missing secret must stop the process. The alternative, a fallback, is how a
service ends up running in the open with a key that is in a public repository,
and it fails silently by construction: everything works.
"""

from __future__ import annotations

import os

from ampeer.settings.base import *  # noqa: F403


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set; refusing to start")
    return value


DEBUG = False
SECRET_KEY = _required("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = [host for host in _required("DJANGO_ALLOWED_HOSTS").split(",") if host]
AMPEER_NEDU_PROFILE_PATH = _required("AMPEER_NEDU_PROFILE_PATH")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _required("POSTGRES_DB"),
        "USER": _required("POSTGRES_USER"),
        "PASSWORD": _required("POSTGRES_PASSWORD"),
        "HOST": _required("POSTGRES_HOST"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
```

`backend/ampeer/settings/__init__.py` and `backend/ampeer/__init__.py` are empty files.

`backend/ampeer/urls.py`:

```python
"""Root URL configuration. Task 6 adds the one include."""

from __future__ import annotations

from django.urls import URLPattern, URLResolver

urlpatterns: list[URLPattern | URLResolver] = []
```

`backend/ampeer/wsgi.py`:

```python
from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ampeer.settings.prod")
application = get_wsgi_application()
```

`backend/manage.py`:

```python
#!/usr/bin/env python
from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ampeer.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

`backend/advice/__init__.py` is empty. `backend/advice/apps.py`:

```python
from __future__ import annotations

from django.apps import AppConfig


class AdviceConfig(AppConfig):
    name = "advice"
    verbose_name = "Advies"
```

- [ ] **Step 3: Write the failing test for the settings**

`tests/test_backend_settings.py`:

```python
"""The settings decide security properties, so they are tested like code.

Production settings are never imported by any other test, so without this file
they would be measured at zero coverage and, worse, a typo in them would first
be discovered on the server.
"""

from __future__ import annotations

import importlib
import sys

import pytest

REQUIRED_ENV = {
    "DJANGO_SECRET_KEY": "x" * 50,
    "DJANGO_ALLOWED_HOSTS": "ampeer.nl,www.ampeer.nl",
    "AMPEER_NEDU_PROFILE_PATH": "/srv/ampeer/nedu-profiles-2025.csv",
    "POSTGRES_DB": "ampeer",
    "POSTGRES_USER": "ampeer",
    "POSTGRES_PASSWORD": "secret",
    "POSTGRES_HOST": "db",
}


def _load_prod(monkeypatch: pytest.MonkeyPatch, **overrides: str | None):
    env = REQUIRED_ENV | overrides
    for name, value in env.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    sys.modules.pop("ampeer.settings.prod", None)
    return importlib.import_module("ampeer.settings.prod")


@pytest.mark.parametrize("missing", sorted(REQUIRED_ENV))
def test_production_refuses_to_start_without_any_required_secret(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    """A default for any of these is a service running in the open."""
    with pytest.raises(RuntimeError, match=missing):
        _load_prod(monkeypatch, **{missing: None})


def test_production_never_runs_with_debug_on(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _load_prod(monkeypatch).DEBUG is False


def test_production_sets_the_transport_and_framing_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prod = _load_prod(monkeypatch)
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SECURE_HSTS_SECONDS >= 31_536_000
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod.X_FRAME_OPTIONS == "DENY"


def test_production_allows_only_the_hosts_it_was_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wildcard here defeats the Host header check entirely."""
    prod = _load_prod(monkeypatch)
    assert prod.ALLOWED_HOSTS == ["ampeer.nl", "www.ampeer.nl"]
    assert "*" not in prod.ALLOWED_HOSTS


def test_nothing_authenticates_because_there_is_nothing_to_log_in_to() -> None:
    from django.conf import settings

    assert settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == []
    assert "django.contrib.auth" not in settings.INSTALLED_APPS
    assert "django.contrib.sessions" not in settings.INSTALLED_APPS
    assert "django.contrib.admin" not in settings.INSTALLED_APPS


def test_both_public_throttle_scopes_are_configured() -> None:
    from django.conf import settings

    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert rates["advice-compute"] == "20/hour"
    assert rates["advice-read"] == "120/hour"
```

`tests/conftest.py`:

```python
"""Shared fixtures.

Throttling stays switched on in tests, because a rate limit that is disabled in
the only place it is exercised is a rate limit nobody has ever seen work. The
cost is that one test's requests would otherwise count against the next one's
budget, which this clears.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _clear_throttle_history() -> Iterator[None]:
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
```

- [ ] **Step 4: Run the settings tests and watch them fail**

Run: `uv run --no-sync pytest tests/test_backend_settings.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'ampeer'`, until Step 2's files exist and `pythonpath = ["backend"]` is in place. With them present: PASS.

- [ ] **Step 5: Extend the boundary test in both directions**

In `tests/test_boundaries.py`, add `backend` to the forbidden set for the pure packages
and add the reverse check. Replace the `test_packages_never_import_django` function and
add one below it:

```python
FORBIDDEN_IN_PURE_PACKAGES = {"django", "rest_framework", "backend", "advice", "ampeer"}

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent / "backend"


def test_packages_never_import_django_or_the_backend() -> None:
    """The pure packages must stay runnable without a database or a server.

    This is the one part of the system where a fault produces a plausible wrong
    number rather than an error message, so it has to be testable and
    validatable on its own.
    """
    offenders = [
        f"{path}: {sorted(_imported_module_names(path) & FORBIDDEN_IN_PURE_PACKAGES)}"
        for root in PACKAGE_ROOTS
        for path in root.rglob("*.py")
        if _imported_module_names(path) & FORBIDDEN_IN_PURE_PACKAGES
    ]
    assert offenders == [], f"pure packages must not import django or backend: {offenders}"


def test_the_backend_may_import_the_pure_packages() -> None:
    """The dependency runs one way, and this proves it actually runs at all.

    A one-directional rule tested only in the forbidding direction stays green
    when the arrow disappears entirely, so this asserts the arrow is there.
    """
    importers = {
        path.name
        for path in BACKEND_ROOT.rglob("*.py")
        if {"ampeer_sim", "ampeer_advice"} & _imported_module_names(path)
    }
    assert importers, "no file under backend/ imports the engine; the seam is missing"
```

- [ ] **Step 6: Close the gap that would exempt the new code from the coverage gate**

`test_every_top_level_package_is_measured_for_coverage` globs `*/__init__.py` at the
repository root. `backend/` has no `__init__.py` there, so every Django app added under
it would be outside the coverage source while the gate stayed green. That is the exact
failure this test was written to prevent, one directory deeper.

In `tests/test_pipeline_contract.py`, replace that test and add one beside it:

```python
def test_every_package_is_measured_for_coverage() -> None:
    """A new package must not be exempt from the gates while they stay green.

    Both levels are checked. The first version of this globbed only the
    repository root, which would have let every Django app under backend/ in
    without being measured.
    """
    roots = {
        path.parent.name
        for path in REPO_ROOT.glob("*/__init__.py")
        if not path.parent.name.startswith(".")
    }
    measured = set(_pyproject()["tool"]["coverage"]["run"]["source"])
    assert roots <= measured, f"packages outside coverage: {sorted(roots - measured)}"

    backend = REPO_ROOT / "backend"
    if backend.is_dir():
        assert "backend" in measured, "backend/ exists but is not measured for coverage"
        apps = {path.parent.name for path in backend.glob("*/__init__.py")}
        assert apps, "backend/ holds no python package; check this test still applies"


def test_the_coverage_omit_list_stays_short_and_justified() -> None:
    """An omit entry is the quietest way to make a coverage floor stop meaning
    anything: the percentage stays high because the untested code is no longer
    counted. Only the two generated entry points may be listed."""
    omitted = set(_pyproject()["tool"]["coverage"]["run"].get("omit", []))
    assert omitted <= {"backend/manage.py", "backend/ampeer/wsgi.py"}, (
        f"unjustified coverage omissions: {sorted(omitted - {'backend/manage.py', 'backend/ampeer/wsgi.py'})}"
    )
```

Add a check that the service container image is pinned by digest, next to the existing
one for actions:

```python
def test_every_service_container_is_pinned_by_digest() -> None:
    """A tag is mutable. `postgres:16-alpine` on Tuesday and on Thursday are two
    different images, and the pipeline already refuses an action pinned by tag
    for exactly that reason."""
    offenders = [
        f"{name}.{service}: {config['image']}"
        for name, job in _jobs().items()
        for service, config in (job.get("services") or {}).items()
        if "@sha256:" not in str(config.get("image", ""))
    ]
    assert not offenders, f"service containers not pinned by digest: {offenders}"
```

- [ ] **Step 7: Give the `test` job a database**

In `.github/workflows/ci.yml`, inside the `test` job, above `steps:`:

```yaml
    services:
      postgres:
        # Digest resolved from Docker Hub on 2026-08-21 for postgres:16-alpine.
        # Pinned rather than tagged for the same reason every action here is
        # pinned: a tag is a name someone else can repoint.
        image: postgres@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685
        env:
          POSTGRES_DB: ampeer
          POSTGRES_USER: ampeer
          POSTGRES_PASSWORD: ampeer
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U ampeer"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
```

Change the two commands in that job so the backend group is installed and the database
is reachable:

```yaml
      - run: uv sync --locked --group dev --group backend
      - run: uv run pytest --cov --cov-report=term-missing
        env:
          POSTGRES_HOST: 127.0.0.1
          POSTGRES_PORT: "5432"
          POSTGRES_DB: ampeer
          POSTGRES_USER: ampeer
          POSTGRES_PASSWORD: ampeer
```

In the `quality` job, extend the three tool invocations to cover the new tree and install
the backend group so the stubs resolve:

```yaml
      - run: uv sync --locked --group dev --group backend
      - run: uv run ruff check ampeer_sim ampeer_advice backend tests tools
      - run: uv run ruff format --check ampeer_sim ampeer_advice backend tests tools
      - run: uv run mypy ampeer_sim ampeer_advice backend tools
```

- [ ] **Step 8: Verify the whole foundation**

Run: `uv run --no-sync pytest tests/test_backend_settings.py tests/test_boundaries.py tests/test_pipeline_contract.py -v`
Expected: PASS.

Run: `uv run --no-sync mypy backend`
Expected: `Success: no issues found`.

Then deliberately break each new gate and confirm it bites, because three checks in this
repository were decoration in their first version and were only found that way:

1. Add `import django` to `ampeer_sim/timebase.py`, run the boundary test, expect FAIL, revert.
2. Change the ci.yml image to `postgres:16-alpine`, run the contract test, expect FAIL, revert.
3. Add `"backend/advice/service.py"` to the coverage `omit` list, run the contract test, expect FAIL, revert.

Report the output of all three. A gate that has never been seen red is not a gate.

- [ ] **Step 9: Stop. Do not commit.** Report to the barrier.

**Correction, recorded 2026-08-21 after this task ran.** Step 5's
`test_the_backend_may_import_the_pure_packages` **cannot pass at the end of Task 1, and
that is a defect in this plan rather than in the work.** Everything Task 1 creates is a
settings module or an entry point, and none of them has any business importing the
engine. The first backend file that legitimately imports it is `serializers.py` in Lane B.

The test is correct and stays exactly as written: a one-directional rule tested only in
the forbidding direction stays green when the arrow disappears altogether, so asserting
the arrow exists is the point. What was wrong is where the plan put it. It is expected
red from the end of Task 1 until the first lane lands, and it going green is the
confirmation that the seam exists. The foundation lane reported this rather than
manufacturing an import to green it, which is rule 6 working.

**Environment note.** Tasks 2, 4 and 6 need a running PostgreSQL; Tasks 1, 3 and 5 do
not, and their tests must not be marked `django_db`. On a machine without one:

```bash
docker run -d --name ampeer-test-db -p 127.0.0.1:55432:5432 \
  -e POSTGRES_DB=ampeer -e POSTGRES_USER=ampeer -e POSTGRES_PASSWORD=ampeer \
  postgres@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685
```

Then prefix every database-touching command with `POSTGRES_PORT=55432`, which
`settings/dev.py` already reads from the environment.

Three deliberate choices in that one command. Bound to `127.0.0.1`, so a development
database with a throwaway password is not reachable from the network. The same digest as
CI, so the schema under test locally is the schema under test in the pipeline. And host
port **55432** rather than 5432, because another project on this machine starts a Postgres
on the default port with Docker Desktop; taking 5432 would have meant either failing to
start or, far worse, silently running the test suite against somebody else's database.
Nothing belonging to another project is stopped or reconfigured.

The port lives in an environment variable rather than in a settings file on purpose. CI
runs a service container on 5432 and a settings file that hardcoded 55432 would work
everywhere except the place the gate runs.

**Formatting a generated file.** After `makemigrations`, run `ruff format` on the new
migration: Django writes it in its own style and the `ruff format --check` gate does not
care who wrote it. More generally, a lane may run `ruff format` in write mode against the
paths in its ownership row. That writes nothing outside those paths, so rule 5's blanket
ban on formatters in a lane was too broad; what rule 5 is actually about is
`pre-commit run --all-files` and any other tool that rewrites the whole tree.

---

## Phase 1: four concurrent lanes

Lanes A, B, C and D start together, after Task 1 is verified. Each writes only the files
in its ownership row.

### Task 2 (Lane A): Storage, and an audit log that resists a careless edit

**Files:**
- Create: `backend/advice/models.py`, `backend/advice/migrations/__init__.py`, `backend/advice/migrations/0001_initial.py`, `backend/advice/management/__init__.py`, `backend/advice/management/commands/__init__.py`, `backend/advice/management/commands/purge_expired_advice.py`
- Test: `tests/test_advice_models.py`

**Interfaces:**
- Consumes: Django app label `advice`, setting `AMPEER_ADVICE_TTL_DAYS` (Task 1).
- Produces:
  - `StoredAdvice` with fields `token: str`, `created_at: datetime`, `expires_at: datetime`, `inputs: dict`, `advice: dict`; classmethod `StoredAdvice.create(inputs: dict, advice: dict) -> StoredAdvice`; classmethod `StoredAdvice.get_live(token: str) -> StoredAdvice | None`.
  - `AuditEvent` with fields `event_type: str`, `occurred_at: datetime`, `context: dict`; constant `AuditEvent.ADVICE_GENERATED = "ADVICE_GENERATED"`; classmethod `AuditEvent.record(event_type: str, **context: object) -> AuditEvent`.
  - `ProductionCache` with fields `postcode4: str`, `azimuth_deg: int`, `tilt_deg: int`, `weather_year: int`, `production_w_per_kwp: bytes`, `temperature_c: bytes`, `source: str`, `fetched_at: datetime`.
  - Management command `purge_expired_advice`.

- [ ] **Step 1: Write the failing tests**

`tests/test_advice_models.py`:

```python
"""The three tables, and the two promises made about them.

A stored advice must hold nothing that identifies a person, and an audit log
must not be quietly rewritable. Neither is enforced by the database, so both are
enforced here.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from advice.models import AuditEvent, ProductionCache, StoredAdvice

pytestmark = pytest.mark.django_db

INPUTS = {"postcode4": "5401", "peak_power_wp": 3500, "annual_consumption_kwh": 3500}
ADVICE = {"confidence": "INDICATIVE", "headline": {"p50": "700.08"}}


def test_a_stored_advice_gets_an_unguessable_token() -> None:
    stored = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    assert len(stored.token) == 22, stored.token
    assert re.fullmatch(r"[A-Za-z0-9_-]{22}", stored.token)


def test_two_stored_advices_never_share_a_token() -> None:
    first = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    second = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    assert first.token != second.token


def test_a_stored_advice_expires_ninety_days_after_it_was_made() -> None:
    stored = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    assert stored.expires_at - stored.created_at == timedelta(days=90)


def test_a_live_token_is_found_and_an_unknown_one_is_not() -> None:
    stored = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    assert StoredAdvice.get_live(stored.token) == stored
    assert StoredAdvice.get_live("nope-nope-nope-nope-no") is None


def test_an_expired_advice_is_gone_rather_than_stale() -> None:
    """Returning old content past its retention date is the worse failure of
    the two: nobody finds out, and the record was supposed to be deleted."""
    stored = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    StoredAdvice.objects.filter(pk=stored.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert StoredAdvice.get_live(stored.token) is None


def test_the_stored_record_holds_no_field_that_could_identify_a_person() -> None:
    """Quarter-hour energy data says when somebody is home. The four digit
    postcode is the deliberate limit; a fifth character, a name or an address
    would change what this table is."""
    forbidden = {"name", "naam", "email", "e_mail", "phone", "telefoon", "address", "adres", "ip"}
    field_names = {field.name for field in StoredAdvice._meta.get_fields()}
    assert not field_names & forbidden, sorted(field_names & forbidden)
    assert "postcode" not in field_names, "only postcode4 belongs here, and only inside inputs"


def test_the_purge_command_deletes_only_what_has_expired() -> None:
    live = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    dead = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    StoredAdvice.objects.filter(pk=dead.pk).update(expires_at=timezone.now() - timedelta(days=1))
    call_command("purge_expired_advice")
    assert list(StoredAdvice.objects.values_list("pk", flat=True)) == [live.pk]


def test_an_audit_event_records_what_happened() -> None:
    event = AuditEvent.record(AuditEvent.ADVICE_GENERATED, token="abc", postcode4="5401")
    assert event.event_type == "ADVICE_GENERATED"
    assert event.context == {"token": "abc", "postcode4": "5401"}
    assert event.occurred_at is not None


def test_an_audit_event_cannot_be_changed_after_the_fact() -> None:
    event = AuditEvent.record(AuditEvent.ADVICE_GENERATED, token="abc")
    event.context = {"token": "rewritten"}
    with pytest.raises(ValueError, match="append-only"):
        event.save()


def test_an_audit_event_cannot_be_deleted() -> None:
    event = AuditEvent.record(AuditEvent.ADVICE_GENERATED, token="abc")
    with pytest.raises(ValueError, match="append-only"):
        event.delete()


def test_an_audit_log_cannot_be_wiped_through_a_queryset() -> None:
    """The instance methods are the obvious guard and the useless one.
    `AuditEvent.objects.filter(...).delete()` never touches them, and that is
    the call somebody actually reaches for."""
    AuditEvent.record(AuditEvent.ADVICE_GENERATED, token="abc")
    with pytest.raises(ValueError, match="append-only"):
        with transaction.atomic():
            AuditEvent.objects.all().delete()
    with pytest.raises(ValueError, match="append-only"):
        with transaction.atomic():
            AuditEvent.objects.all().update(event_type="X")
    assert AuditEvent.objects.count() == 1


def test_the_audit_log_holds_no_ip_address() -> None:
    """An audit log is a record of what the service did, not of who visited."""
    field_names = {field.name for field in AuditEvent._meta.get_fields()}
    assert "ip" not in field_names and "ip_address" not in field_names


def test_a_production_cache_row_is_unique_per_roof_and_year() -> None:
    from django.db.utils import IntegrityError

    ProductionCache.objects.create(
        postcode4="5401",
        azimuth_deg=0,
        tilt_deg=35,
        weather_year=2023,
        production_w_per_kwp=b"a",
        temperature_c=b"b",
        source="PVGIS",
    )
    with pytest.raises(IntegrityError):
        ProductionCache.objects.create(
            postcode4="5401",
            azimuth_deg=0,
            tilt_deg=35,
            weather_year=2023,
            production_w_per_kwp=b"c",
            temperature_c=b"d",
            source="PVGIS",
        )
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run --no-sync pytest tests/test_advice_models.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'advice.models'`.

- [ ] **Step 3: Write the models**

`backend/advice/models.py`:

```python
"""The three tables the advice API keeps.

None of them holds a personal detail. `StoredAdvice.inputs` holds the answers a
visitor gave, and the serializer that produces it accepts a four digit postcode
and nothing longer, so there is no address in here and no way to put one in.
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any, Self

from django.conf import settings
from django.db import models
from django.utils import timezone

#: 16 random bytes rendered as 22 url-safe characters. At 128 bits a collision
#: is not something to write a retry loop for, and the unique constraint below
#: turns the impossible case into an error rather than an overwrite.
TOKEN_BYTES = 16


class StoredAdvice(models.Model):
    """One computed advice, retrievable by its token until it expires."""

    token = models.CharField(max_length=32, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    #: The validated answers, so the advice can be recomputed and defended.
    inputs = models.JSONField()
    #: The rendered advice, including engine_version and advice_version.
    advice = models.JSONField()

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def create(cls, inputs: dict[str, Any], advice: dict[str, Any]) -> Self:
        now = timezone.now()
        return cls.objects.create(
            token=secrets.token_urlsafe(TOKEN_BYTES),
            expires_at=now + timedelta(days=settings.AMPEER_ADVICE_TTL_DAYS),
            inputs=inputs,
            advice=advice,
        )

    @classmethod
    def get_live(cls, token: str) -> Self | None:
        """Return the advice for this token, or None if it never existed or has
        expired. Both cases answer the same way on purpose: telling a caller
        that a token used to exist is telling them something."""
        return cls.objects.filter(token=token, expires_at__gt=timezone.now()).first()


class AppendOnlyQuerySet(models.QuerySet["AuditEvent"]):
    """The instance guards below are the obvious half and the weaker half.

    `AuditEvent.objects.filter(...).delete()` never calls `Model.delete`, and
    that is the call a developer reaches for when a table is in the way.
    """

    def delete(self) -> Any:
        raise ValueError("the audit log is append-only: rows cannot be deleted")

    def update(self, **kwargs: Any) -> int:
        raise ValueError("the audit log is append-only: rows cannot be updated")


class AuditEvent(models.Model):
    """One line in the append-only log.

    Append-only is enforced in Python, not in the database. That is not a
    defence against anyone with a database connection and it is not meant to be.
    It is a defence against the ordinary way an audit log dies, which is a later
    developer running update_or_create over it without thinking about it.
    """

    ADVICE_GENERATED = "ADVICE_GENERATED"

    event_type = models.CharField(max_length=64, db_index=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    #: Context without a personal detail: the token and the four digit
    #: postcode, never the IP address of the visitor.
    context = models.JSONField(default=dict)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["-occurred_at"]

    @classmethod
    def record(cls, event_type: str, **context: object) -> AuditEvent:
        return cls.objects.create(event_type=event_type, context=dict(context))

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise ValueError("the audit log is append-only: rows cannot be updated")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("the audit log is append-only: rows cannot be deleted")


class ProductionCache(models.Model):
    """One PVGIS answer, kept so a visitor never waits for an external service.

    The orientation columns are whole degrees and integers. A float key would
    miss its own entry on 35.000000001, and a rounded lookup against a float key
    would hand back a series computed for a different roof than the simulation
    then assumes. Rounding happens once, in the serializer.

    There is no expiry. PVGIS data about a closed weather year does not change.
    `fetched_at` exists so a later cleanup remains possible.
    """

    postcode4 = models.CharField(max_length=4)
    azimuth_deg = models.SmallIntegerField()
    tilt_deg = models.SmallIntegerField()
    weather_year = models.SmallIntegerField()
    production_w_per_kwp = models.BinaryField()
    temperature_c = models.BinaryField()
    source = models.CharField(max_length=16)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["postcode4", "azimuth_deg", "tilt_deg", "weather_year"],
                name="unique_production_cache_key",
            )
        ]
```

- [ ] **Step 4: Write the purge command**

`backend/advice/management/commands/purge_expired_advice.py`:

```python
"""Delete advices past their retention date.

Called by cron, not by Celery. A daily DELETE over a table with an index on
expires_at does not need a task queue, and a task queue is four moving parts
that can fail silently while the deletion quietly stops happening.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from advice.models import StoredAdvice


class Command(BaseCommand):
    help = "Delete stored advices whose retention period has passed"

    def handle(self, *args: Any, **options: Any) -> None:
        deleted, _ = StoredAdvice.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(f"deleted {deleted} expired advice(s)")
```

Create the two empty `__init__.py` files under `management/` and `management/commands/`.

- [ ] **Step 5: Generate the migration**

Run: `uv run --no-sync python backend/manage.py makemigrations advice --settings ampeer.settings.test`
Expected: `0001_initial.py` created with three models.

Read the generated file and confirm it contains the unique constraint on
`ProductionCache` and the index on `StoredAdvice.expires_at`. A migration nobody read is
a schema nobody chose.

- [ ] **Step 6: Run the tests**

Run: `uv run --no-sync pytest tests/test_advice_models.py -v`
Expected: PASS, 13 tests.

Run: `uv run --no-sync mypy backend/advice/models.py`
Expected: `Success: no issues found`.

Run: `uv run --no-sync ruff check backend/advice tests/test_advice_models.py`
Expected: no findings.

- [ ] **Step 7: Stop. Do not commit.** Report the three command outputs to the barrier.

---

### Task 3 (Lane B): Input validation, the only place untrusted data is shaped

**Files:**
- Create: `backend/advice/serializers.py`
- Test: `tests/test_advice_serializers.py`

**Interfaces:**
- Consumes: nothing from other lanes.
- Produces:
  - `EstimateInputSerializer` and `RefineInputSerializer`, both DRF `Serializer` subclasses.
  - Both expose `QUESTION_COUNT: int` as a class attribute: `4` on estimate, `9` on refine.
  - `validated_data` keys on estimate: `postcode4: str`, `peak_power_wp: int`, `azimuth_deg: int`, `tilt_deg: int`, `annual_consumption_kwh: float`.
  - Refine adds: `daytime_occupancy: bool`, `has_ev: bool`, `ev_behaviour: str | None`, `has_heat_pump: bool`, `heat_demand_kwh: float | None`, `dynamic_contract: bool`, `has_battery: bool`, `battery_capacity_kwh: float | None`.
  - `ev_behaviour` is one of the `EVChargingBehaviour` enum names.

- [ ] **Step 1: Write the failing tests**

`tests/test_advice_serializers.py`:

```python
"""Validation is the boundary between a stranger's JSON and the model.

Two properties matter more than any individual rule. Unknown fields are
refused rather than ignored, so nothing can be smuggled into the stored record.
And every numeric field has an upper bound, because an unbounded number here is
not a wrong answer, it is a way to make the server compute for a long time.
"""

from __future__ import annotations

import pytest

from advice.serializers import EstimateInputSerializer, RefineInputSerializer

VALID_ESTIMATE = {
    "postcode4": "5401",
    "peak_power_wp": 3500,
    "azimuth_deg": 0,
    "tilt_deg": 35,
    "annual_consumption_kwh": 3500,
}

VALID_REFINE = VALID_ESTIMATE | {
    "daytime_occupancy": True,
    "has_ev": True,
    "ev_behaviour": "IMMEDIATE",
    "has_heat_pump": False,
    "heat_demand_kwh": None,
    "dynamic_contract": False,
    "has_battery": False,
    "battery_capacity_kwh": None,
}


def test_a_complete_estimate_validates() -> None:
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["postcode4"] == "5401"


def test_the_two_rounds_declare_how_many_questions_they_asked() -> None:
    """The confidence label is derived from this count, and nothing else can
    derive it: a frozen dataclass cannot tell 'nobody is home' apart from the
    default that says the same thing. Round one asks four questions and yields
    five values, because orientation and tilt are one question about one roof."""
    assert EstimateInputSerializer.QUESTION_COUNT == 4
    assert RefineInputSerializer.QUESTION_COUNT == 9


@pytest.mark.parametrize("postcode", ["540", "54011", "54O1", "", "1234 AB", " 5401"])
def test_a_postcode_that_is_not_four_digits_is_refused(postcode: str) -> None:
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"postcode4": postcode})
    assert not serializer.is_valid()
    assert "postcode4" in serializer.errors


def test_a_full_postcode_cannot_be_submitted() -> None:
    """Storing six characters instead of four changes what this table is:
    four digits is a neighbourhood, six is a street."""
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"postcode4": "5401AB"})
    assert not serializer.is_valid()


def test_an_unknown_field_is_refused_rather_than_ignored() -> None:
    """DRF drops unknown keys by default. Dropping them silently means a caller
    can send `email` forever and believe it is stored, and it means a typo in a
    real field name is accepted as an omission."""
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"email": "a@b.nl"})
    assert not serializer.is_valid()
    assert "email" in str(serializer.errors)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("peak_power_wp", 0),
        ("peak_power_wp", -1000),
        ("peak_power_wp", 10_000_000),
        ("annual_consumption_kwh", -1.0),
        ("annual_consumption_kwh", 0.0),
        ("annual_consumption_kwh", 10_000_000.0),
        ("tilt_deg", -1),
        ("tilt_deg", 91),
        ("azimuth_deg", -181),
        ("azimuth_deg", 181),
    ],
)
def test_every_number_is_bounded_on_both_sides(field: str, value: float) -> None:
    """An unbounded input is not a wrong answer, it is a way to make the server
    work. A 10 MWp array is 243 simulations of a power station."""
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {field: value})
    assert not serializer.is_valid(), f"{field}={value} was accepted"
    assert field in serializer.errors


def test_a_fractional_roof_angle_is_rounded_to_a_whole_degree() -> None:
    """One value flows into the cache key, the PVGIS call and the PVSystem.
    Rounding anywhere else would mean the cached series describes a slightly
    different roof than the simulation assumes."""
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"tilt_deg": 34.6})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["tilt_deg"] == 35
    assert isinstance(serializer.validated_data["tilt_deg"], int)


def test_a_complete_refine_validates() -> None:
    serializer = RefineInputSerializer(data=VALID_REFINE)
    assert serializer.is_valid(), serializer.errors


def test_an_unknown_charging_behaviour_is_refused() -> None:
    serializer = RefineInputSerializer(data=VALID_REFINE | {"ev_behaviour": "WHENEVER"})
    assert not serializer.is_valid()
    assert "ev_behaviour" in serializer.errors


def test_claiming_an_ev_without_saying_when_it_charges_is_refused() -> None:
    """The charging moment is most of the answer for a household with an EV.
    Filling it in with a default would be inventing the input that matters
    most."""
    serializer = RefineInputSerializer(data=VALID_REFINE | {"ev_behaviour": None})
    assert not serializer.is_valid()


def test_claiming_a_battery_without_a_capacity_is_refused() -> None:
    serializer = RefineInputSerializer(
        data=VALID_REFINE | {"has_battery": True, "battery_capacity_kwh": None}
    )
    assert not serializer.is_valid()


def test_a_capacity_without_a_battery_is_refused() -> None:
    """Two fields that contradict each other must not both be stored: whichever
    one the assembly happens to read decides the answer."""
    serializer = RefineInputSerializer(
        data=VALID_REFINE | {"has_battery": False, "battery_capacity_kwh": 10.0}
    )
    assert not serializer.is_valid()


def test_claiming_a_heat_pump_without_a_heat_demand_is_refused() -> None:
    serializer = RefineInputSerializer(
        data=VALID_REFINE | {"has_heat_pump": True, "heat_demand_kwh": None}
    )
    assert not serializer.is_valid()


def test_a_battery_larger_than_any_home_battery_is_refused() -> None:
    serializer = RefineInputSerializer(
        data=VALID_REFINE | {"has_battery": True, "battery_capacity_kwh": 5_000.0}
    )
    assert not serializer.is_valid()
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run --no-sync pytest tests/test_advice_serializers.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'advice.serializers'`.

- [ ] **Step 3: Write the serializers**

`backend/advice/serializers.py`:

```python
"""Where a stranger's JSON becomes something the model may see.

Two rules run through everything below. Unknown fields are refused rather than
dropped, because a silently ignored field means a caller can send an email
address forever and believe it was stored, and a typo in a real field name reads
as an omission. And every number is bounded on both sides, because an unbounded
number is not a wrong answer but a way to make the server compute.
"""

from __future__ import annotations

from typing import Any, ClassVar

from rest_framework import serializers

from ampeer_sim.types import EVChargingBehaviour

#: Bounds chosen to be wide enough that no real household is refused, and
#: narrow enough that no single request can occupy the machine. A domestic
#: array above 30 kWp is not a household, and 50 MWh a year is a factory.
MAX_PEAK_POWER_WP = 30_000
MAX_ANNUAL_CONSUMPTION_KWH = 50_000.0
MAX_HEAT_DEMAND_KWH = 40_000.0
#: The largest home battery on the Dutch market is well under this.
MAX_BATTERY_CAPACITY_KWH = 100.0


class StrictSerializer(serializers.Serializer[dict[str, Any]]):
    """A serializer that refuses what it does not recognise."""

    def to_internal_value(self, data: Any) -> Any:
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {name: "onbekend veld" for name in sorted(unknown)}
                )
        return super().to_internal_value(data)


class EstimateInputSerializer(StrictSerializer):
    """Round one: four questions, five values.

    Orientation and tilt are one question about one roof, which is why the
    question count below is four and not five. That count decides the
    confidence label, so it is a property of the form and not of this class's
    field list.
    """

    QUESTION_COUNT: ClassVar[int] = 4

    postcode4 = serializers.RegexField(r"^\d{4}$")
    peak_power_wp = serializers.IntegerField(min_value=1, max_value=MAX_PEAK_POWER_WP)
    # Rounded to whole degrees here and nowhere else, so one value reaches the
    # cache key, the PVGIS call and the PVSystem. Zero is south, negative is
    # east, positive is west, matching PVGIS and ampeer_sim.
    azimuth_deg = serializers.IntegerField(min_value=-180, max_value=180)
    tilt_deg = serializers.IntegerField(min_value=0, max_value=90)
    annual_consumption_kwh = serializers.FloatField(
        min_value=1.0, max_value=MAX_ANNUAL_CONSUMPTION_KWH
    )

    def to_internal_value(self, data: Any) -> Any:
        # IntegerField refuses 34.6 outright. Rounding before validation keeps
        # a slider that emits fractions working, without letting a float reach
        # the cache key.
        if isinstance(data, dict):
            data = dict(data)
            for name in ("azimuth_deg", "tilt_deg"):
                value = data.get(name)
                if isinstance(value, float):
                    data[name] = round(value)
        return super().to_internal_value(data)


class RefineInputSerializer(EstimateInputSerializer):
    """Round two: five more questions, nine in total."""

    QUESTION_COUNT: ClassVar[int] = 9

    daytime_occupancy = serializers.BooleanField()
    has_ev = serializers.BooleanField()
    ev_behaviour = serializers.ChoiceField(
        choices=[behaviour.name for behaviour in EVChargingBehaviour],
        allow_null=True,
        required=False,
        default=None,
    )
    has_heat_pump = serializers.BooleanField()
    heat_demand_kwh = serializers.FloatField(
        min_value=1.0, max_value=MAX_HEAT_DEMAND_KWH, allow_null=True, required=False, default=None
    )
    dynamic_contract = serializers.BooleanField()
    has_battery = serializers.BooleanField()
    battery_capacity_kwh = serializers.FloatField(
        min_value=0.5,
        max_value=MAX_BATTERY_CAPACITY_KWH,
        allow_null=True,
        required=False,
        default=None,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Every yes must bring the detail that makes it usable.

        A default here would be an invented number in the place it matters
        most: when an EV charges decides most of the answer for a household
        that has one. And a capacity without a battery is two fields that
        disagree, where whichever one the assembly reads first decides the
        result.
        """
        errors: dict[str, str] = {}
        if attrs["has_ev"] and attrs.get("ev_behaviour") is None:
            errors["ev_behaviour"] = "verplicht wanneer er een elektrische auto is"
        if not attrs["has_ev"] and attrs.get("ev_behaviour") is not None:
            errors["ev_behaviour"] = "alleen toegestaan met een elektrische auto"
        if attrs["has_heat_pump"] and attrs.get("heat_demand_kwh") is None:
            errors["heat_demand_kwh"] = "verplicht wanneer er een warmtepomp is"
        if not attrs["has_heat_pump"] and attrs.get("heat_demand_kwh") is not None:
            errors["heat_demand_kwh"] = "alleen toegestaan met een warmtepomp"
        if attrs["has_battery"] and attrs.get("battery_capacity_kwh") is None:
            errors["battery_capacity_kwh"] = "verplicht wanneer er een thuisbatterij is"
        if not attrs["has_battery"] and attrs.get("battery_capacity_kwh") is not None:
            errors["battery_capacity_kwh"] = "alleen toegestaan met een thuisbatterij"
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
```

The Dutch strings above are validation messages, not advice text. They stay here rather
than in `nl.py` because `nl.py` is keyed by rule id and belongs to the pure advice
package, which must not know that an HTTP form exists. Task 8's audit checks that no
advice sentence leaked in with them.

- [ ] **Step 4: Run the tests**

Run: `uv run --no-sync pytest tests/test_advice_serializers.py -v`
Expected: PASS, 27 tests including the parametrized cases.

Run: `uv run --no-sync mypy backend/advice/serializers.py`
Expected: `Success: no issues found`.

Run: `uv run --no-sync ruff check backend/advice/serializers.py tests/test_advice_serializers.py`
Expected: no findings.

- [ ] **Step 5: Stop. Do not commit.** Report the three command outputs to the barrier.

---

### Task 4 (Lane C): The providers, cached and chosen

**Files:**
- Create: `backend/advice/production.py`, `backend/advice/profiles.py`
- Test: `tests/test_advice_providers.py`

**Interfaces:**
- Consumes: `advice.models.ProductionCache` (Task 2) with fields `postcode4`, `azimuth_deg`, `tilt_deg`, `weather_year`, `production_w_per_kwp`, `temperature_c`, `source`; settings `AMPEER_NEDU_PROFILE_PATH`, `AMPEER_WEATHER_YEAR` (Task 1).
- Produces:
  - `CachedProductionProvider(inner: ProductionProvider, weather_year: int)` satisfying `ampeer_sim.providers.ProductionProvider`.
  - `production_provider() -> ProductionProvider`, the one the service uses.
  - `profile_provider() -> ProfileProvider`, the one the service uses.
  - `encode_series(values: np.ndarray) -> bytes` and `decode_series(blob: bytes) -> np.ndarray`.

- [ ] **Step 1: Write the failing tests**

`tests/test_advice_providers.py`:

```python
"""The cache and the two provider choices.

The cache is the reason a visitor never waits for PVGIS. What it must never do
is answer with a series computed for a different roof, which is why the key is
integers and the test below asks for the same roof twice by two routes.
"""

from __future__ import annotations

import numpy as np
import pytest
from django.test import override_settings

from advice.models import ProductionCache
from advice.production import CachedProductionProvider, decode_series, encode_series
from advice.profiles import profile_provider
from ampeer_sim.types import ProductionSource

pytestmark = pytest.mark.django_db

WEATHER_YEAR = 2023


class CountingProvider:
    """A production provider that records how often it was actually asked."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, float, float]] = []

    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        self.calls.append((postcode4, azimuth_deg, tilt_deg))
        production = np.linspace(0.0, 900.0, 8760, dtype=np.float64)
        temperature = np.linspace(-5.0, 30.0, 8760, dtype=np.float64)
        return production, temperature, ProductionSource.PVGIS


def test_a_series_survives_the_round_trip_within_float32_precision() -> None:
    """Stored as float32 on purpose. PVGIS reports irradiance to about three
    significant digits; float32 carries seven. Keeping float64 would double the
    row for precision the source does not have."""
    original = np.linspace(0.0, 900.0, 8760, dtype=np.float64)
    restored = decode_series(encode_series(original))
    assert restored.shape == original.shape
    assert np.allclose(restored, original, rtol=1e-6, atol=1e-3)


def test_the_first_request_asks_the_inner_provider() -> None:
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    production, temperature, source = provider.hourly_series("5401", 0.0, 35.0)
    assert len(inner.calls) == 1
    assert source is ProductionSource.PVGIS
    assert production.shape == (8760,)
    assert temperature.shape == (8760,)


def test_a_second_identical_request_does_not_ask_again() -> None:
    """The definition of done says this in so many words, and a cache that is
    never observed missing is a cache nobody has seen work."""
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    first = provider.hourly_series("5401", 0.0, 35.0)
    second = provider.hourly_series("5401", 0.0, 35.0)
    assert len(inner.calls) == 1, f"the inner provider was asked {len(inner.calls)} times"
    assert np.allclose(first[0], second[0])
    assert first[2] is second[2]


def test_a_different_roof_is_a_different_entry() -> None:
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    provider.hourly_series("5401", 0.0, 35.0)
    provider.hourly_series("5401", 90.0, 35.0)
    provider.hourly_series("5402", 0.0, 35.0)
    assert len(inner.calls) == 3
    assert ProductionCache.objects.count() == 3


def test_two_spellings_of_the_same_roof_hit_the_same_entry() -> None:
    """35.0 and 35 are the same roof. A float somewhere in the key would make
    them two, and the second one would pay for a network call that already
    happened."""
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    provider.hourly_series("5401", 0.0, 35.0)
    provider.hourly_series("5401", 0, 35)
    assert len(inner.calls) == 1
    assert ProductionCache.objects.count() == 1


def test_a_cached_entry_remembers_where_the_data_came_from() -> None:
    """The response reports production_source. A cache that forgot it would
    report PVGIS for a series the offline table produced, which is a confidence
    claim the data does not support."""
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    provider.hourly_series("5401", 0.0, 35.0)
    _, _, source = provider.hourly_series("5401", 0.0, 35.0)
    assert source is ProductionSource.PVGIS
    assert ProductionCache.objects.get().source == "PVGIS"


def test_a_fallback_answer_is_cached_as_a_fallback_answer() -> None:
    class FallbackOnly(CountingProvider):
        def hourly_series(
            self, postcode4: str, azimuth_deg: float, tilt_deg: float
        ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
            production, temperature, _ = super().hourly_series(postcode4, azimuth_deg, tilt_deg)
            return production, temperature, ProductionSource.FALLBACK_TABLE

    provider = CachedProductionProvider(FallbackOnly(), weather_year=WEATHER_YEAR)
    provider.hourly_series("5401", 0.0, 35.0)
    _, _, source = provider.hourly_series("5401", 0.0, 35.0)
    assert source is ProductionSource.FALLBACK_TABLE


def test_a_different_weather_year_is_a_different_entry() -> None:
    inner = CountingProvider()
    CachedProductionProvider(inner, weather_year=2022).hourly_series("5401", 0.0, 35.0)
    CachedProductionProvider(inner, weather_year=2023).hourly_series("5401", 0.0, 35.0)
    assert len(inner.calls) == 2


@override_settings(AMPEER_NEDU_PROFILE_PATH=None)
def test_without_a_profile_file_the_service_refuses_to_answer() -> None:
    """There is no fallback consumption shape and there must not be one. A
    profile nobody measured would be an invented number sitting at the centre
    of every answer, and it would produce a confident wrong result rather than
    an error."""
    with pytest.raises(RuntimeError, match="AMPEER_NEDU_PROFILE_PATH"):
        profile_provider()


@override_settings(AMPEER_NEDU_PROFILE_PATH="/does/not/exist.csv")
def test_a_profile_path_that_points_at_nothing_is_reported_as_such() -> None:
    with pytest.raises(RuntimeError, match="does not exist"):
        profile_provider()
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run --no-sync pytest tests/test_advice_providers.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'advice.production'`.

- [ ] **Step 3: Write the cached production provider**

`backend/advice/production.py`:

```python
"""The PVGIS cache.

One entry is two hourly series for one roof in one weather year. Those
combinations repeat enormously: a four digit postcode area holds thousands of
houses and most roofs sit on a handful of orientations.

It lives in Postgres rather than Redis for two reasons. It has to survive a
restart, or the first visitor after every deploy pays for an external call. And
it keeps Redis out of the request path entirely, which is one fewer thing that
can be down at the moment somebody is on the site.
"""

from __future__ import annotations

import io
import zlib

import numpy as np

from advice.models import ProductionCache
from ampeer_sim.providers import ProductionProvider
from ampeer_sim.types import ProductionSource


def encode_series(values: np.ndarray) -> bytes:
    """Compress an hourly series for storage.

    float32, not float64. PVGIS reports irradiance to roughly three significant
    digits and float32 carries seven, so the second half of a float64 is
    precision the source never had. Halving the row is the whole benefit and
    nothing measurable is lost.
    """
    buffer = io.BytesIO()
    np.save(buffer, np.asarray(values, dtype=np.float32), allow_pickle=False)
    return zlib.compress(buffer.getvalue(), level=6)


def decode_series(blob: bytes) -> np.ndarray:
    """Restore a series as float64, which is what the engine works in."""
    buffer = io.BytesIO(zlib.decompress(bytes(blob)))
    return np.load(buffer, allow_pickle=False).astype(np.float64)


class CachedProductionProvider:
    """A production provider that asks the one behind it at most once per roof."""

    def __init__(self, inner: ProductionProvider, weather_year: int) -> None:
        self._inner = inner
        self._weather_year = weather_year

    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        # Whole degrees, so 35.0 and 35 are one roof rather than two. The
        # serializer already rounds; this makes the cache correct even when it
        # is called from somewhere that did not.
        key = {
            "postcode4": postcode4,
            "azimuth_deg": round(azimuth_deg),
            "tilt_deg": round(tilt_deg),
            "weather_year": self._weather_year,
        }
        cached = ProductionCache.objects.filter(**key).first()
        if cached is not None:
            return (
                decode_series(cached.production_w_per_kwp),
                decode_series(cached.temperature_c),
                ProductionSource[cached.source],
            )

        production, temperature, source = self._inner.hourly_series(
            postcode4, float(key["azimuth_deg"]), float(key["tilt_deg"])
        )
        # get_or_create rather than create: two requests for the same new roof
        # can arrive together, and losing that race must cost a wasted call,
        # never a 500.
        ProductionCache.objects.get_or_create(
            **key,
            defaults={
                "production_w_per_kwp": encode_series(production),
                "temperature_c": encode_series(temperature),
                # The name, not the value: the response reports where the data
                # came from, and a cache that forgot would claim PVGIS for a
                # series the offline table produced.
                "source": source.name,
            },
        )
        return production, temperature, source
```

Add the composition function at the end of the same file:

```python
def production_provider(weather_year: int) -> ProductionProvider:
    """The provider the service uses: cache in front, PVGIS behind, offline
    table behind that. A visitor never waits for an external service and an
    advice never fails because one is slow."""
    from ampeer_sim.production.pvgis import PvgisProvider, ResilientProductionProvider

    return CachedProductionProvider(
        ResilientProductionProvider(PvgisProvider(weather_year)), weather_year=weather_year
    )
```

If the constructor signatures of `PvgisProvider` or `ResilientProductionProvider` differ
from the above, read `ampeer_sim/production/pvgis.py` and match them. Do not change that
file: it is not in this lane's ownership row. If it cannot be called without changing it,
stop and report.

- [ ] **Step 4: Write the profile provider selection**

`backend/advice/profiles.py`:

```python
"""Which consumption profile this deployment uses.

There is exactly one, and there is deliberately no fallback. Every other
external source in this system degrades gracefully: PVGIS falls back to an
offline table built from nine measured years. A consumption profile has no such
table, because nobody has measured one that we may redistribute, and inventing
a shape would put a made-up number at the centre of every answer while every
test stayed green.

So a deployment without the NEDU file refuses to answer. That is worse service
and better honesty, and it keeps the licensing question visible instead of
letting a plausible curve paper over it.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

from ampeer_sim.profiles.nedu import NeduFileProvider
from ampeer_sim.providers import ProfileProvider


def profile_provider() -> ProfileProvider:
    configured = getattr(settings, "AMPEER_NEDU_PROFILE_PATH", None)
    if not configured:
        raise RuntimeError(
            "AMPEER_NEDU_PROFILE_PATH is not set; refusing to answer with an "
            "invented consumption profile"
        )
    path = Path(configured)
    if not path.exists():
        raise RuntimeError(f"AMPEER_NEDU_PROFILE_PATH does not exist: {path}")
    return NeduFileProvider(path)
```

- [ ] **Step 5: Run the tests**

Run: `uv run --no-sync pytest tests/test_advice_providers.py -v`
Expected: PASS, 10 tests.

Run: `uv run --no-sync mypy backend/advice/production.py backend/advice/profiles.py`
Expected: `Success: no issues found`.

- [ ] **Step 6: Measure what an entry actually costs and record it**

Run:

```bash
uv run --no-sync python -c "
import numpy as np, sys
sys.path.insert(0, 'backend')
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ampeer.settings.test')
django.setup()
from advice.production import encode_series
series = np.linspace(0.0, 900.0, 8760)
print('one series compressed:', len(encode_series(series)), 'bytes')
"
```

Put the measured figure in a comment above `encode_series`, phrased as measured on
2026-08-21. Do not write a number you did not see.

- [ ] **Step 7: Stop. Do not commit.** Report the outputs to the barrier.

---

### Task 5 (Lane D): Assembly and rendering

**Files:**
- Create: `backend/advice/assembly.py`, `backend/advice/rendering.py`
- Test: `tests/test_advice_assembly.py`, `tests/test_advice_rendering.py`

**Interfaces:**
- Consumes: validated data shaped as Task 3 produces it (keys listed in Task 3's Produces block). It does not import the serializers; it takes a plain `dict[str, Any]`.
- Produces:
  - `build_household(data: dict[str, Any]) -> Household`
  - `build_pv_system(data: dict[str, Any]) -> PVSystem`
  - `build_battery_spec(data: dict[str, Any]) -> BatterySpec | None`
  - `build_tariffs(data: dict[str, Any]) -> tuple[TariffSet, TariffSet, TariffSet]` returning `(baseline, scenario, dynamic_scenario)`
  - `money(value: Decimal) -> str`
  - `render(advice: Advice, result: Result, token: str) -> dict[str, Any]`

- [ ] **Step 1: Write the failing assembly tests**

`tests/test_advice_assembly.py`:

```python
"""Turning nine answers into the objects the engine takes.

This is where a missing answer becomes a default, so it is where a default can
quietly become an invented input. Every default below is either a documented
national average that already lives in ampeer_sim, or an explicit 'we were not
told', never a guess dressed as an answer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from advice.assembly import build_battery_spec, build_household, build_pv_system, build_tariffs
from ampeer_sim.types import EVChargingBehaviour, ProfileCategory

ESTIMATE: dict[str, Any] = {
    "postcode4": "5401",
    "peak_power_wp": 3500,
    "azimuth_deg": 0,
    "tilt_deg": 35,
    "annual_consumption_kwh": 3500.0,
}

REFINE: dict[str, Any] = ESTIMATE | {
    "daytime_occupancy": True,
    "has_ev": True,
    "ev_behaviour": "IMMEDIATE",
    "has_heat_pump": True,
    "heat_demand_kwh": 6000.0,
    "dynamic_contract": True,
    "has_battery": True,
    "battery_capacity_kwh": 10.0,
}


def test_an_estimate_becomes_a_household_with_nothing_assumed_about_the_extras() -> None:
    household = build_household(ESTIMATE)
    assert household.postcode4 == "5401"
    assert household.annual_consumption_kwh == 3500.0
    assert household.ev is None
    assert household.heat_pump is None
    assert household.profile_category is ProfileCategory.E1A


def test_a_household_that_was_not_asked_is_not_assumed_to_be_home() -> None:
    """Round one never asks. False here is the model's stated default and it is
    also the conservative direction: a household assumed to be home would show
    a higher self-consumption rate and a smaller shock than it will get."""
    assert build_household(ESTIMATE).daytime_occupancy is False


def test_a_refine_carries_every_answer_into_the_household() -> None:
    household = build_household(REFINE)
    assert household.daytime_occupancy is True
    assert household.ev is not None
    assert household.ev.behaviour is EVChargingBehaviour.IMMEDIATE
    assert household.heat_pump is not None
    assert household.heat_pump.heat_demand_kwh == 6000.0


def test_saying_no_to_an_asset_leaves_it_out_entirely() -> None:
    household = build_household(REFINE | {"has_ev": False, "ev_behaviour": None})
    assert household.ev is None


def test_the_roof_becomes_a_pv_system() -> None:
    system = build_pv_system(ESTIMATE)
    assert system.peak_power_wp == 3500
    assert system.azimuth_deg == 0.0
    assert system.tilt_deg == 35.0


def test_a_household_without_a_battery_gets_no_battery_spec() -> None:
    assert build_battery_spec(ESTIMATE) is None
    assert build_battery_spec(REFINE | {"has_battery": False, "battery_capacity_kwh": None}) is None


def test_an_existing_battery_gets_a_spec_scaled_to_its_capacity() -> None:
    """Power is derived from capacity rather than asked. Nobody knows their
    inverter rating, and a 0.5C rate is what domestic systems ship with."""
    spec = build_battery_spec(REFINE)
    assert spec is not None
    assert spec.capacity_kwh == 10.0
    assert spec.max_charge_kw == pytest.approx(5.0)
    assert spec.max_discharge_kw == pytest.approx(5.0)
    assert spec.allow_grid_charging is False


def test_the_baseline_still_has_net_metering_and_the_scenario_does_not() -> None:
    """The whole product is the difference between these two."""
    baseline, scenario, _ = build_tariffs(ESTIMATE)
    assert baseline.net_metering is True
    assert scenario.net_metering is False


def test_a_dynamic_scenario_is_always_built_so_the_rule_can_compare() -> None:
    """CONSIDER_DYNAMIC_CONTRACT needs both to say anything, including for a
    household that already has a dynamic contract and might be better off
    without one."""
    _, scenario, dynamic = build_tariffs(ESTIMATE)
    assert dynamic.dynamic is True
    assert scenario.dynamic is False
    assert dynamic.feed_in_price != scenario.feed_in_price


def test_the_scenario_charges_for_feeding_in() -> None:
    """The correction that halved the headline: the published three to eight
    cent is gross, and the cost per exported kWh eats almost all of it."""
    _, scenario, _ = build_tariffs(ESTIMATE)
    assert scenario.feed_in_cost_per_kwh > Decimal("0")
```

- [ ] **Step 2: Run and watch it fail**

Run: `uv run --no-sync pytest tests/test_advice_assembly.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'advice.assembly'`.

- [ ] **Step 3: Write the assembly**

`backend/advice/assembly.py`:

```python
"""Nine answers into the objects the engine takes.

This is the file where a question nobody answered becomes a default, which
makes it the file where an invented input would enter. Every default here is
either already documented in ampeer_sim as a national average, or an explicit
absence: `ev=None` says we were not told, and the engine treats it that way.
Nothing here guesses a value and presents it as an answer.
"""

from __future__ import annotations

from typing import Any

from ampeer_advice.tariffs import baseline_tariffs, scenario_2027_tariffs
from ampeer_sim.types import (
    EV,
    BatterySpec,
    EVChargingBehaviour,
    HeatPump,
    Household,
    PVSystem,
    TariffSet,
)

#: Charge and discharge power as a fraction of capacity. Domestic batteries
#: ship at roughly 0.5C and nobody knows their inverter rating, so this is
#: derived rather than asked. It is a property of the hardware class, not a
#: guess about this household.
BATTERY_C_RATE = 0.5


def build_household(data: dict[str, Any]) -> Household:
    ev = (
        EV(behaviour=EVChargingBehaviour[data["ev_behaviour"]])
        if data.get("has_ev") and data.get("ev_behaviour")
        else None
    )
    heat_pump = (
        HeatPump(heat_demand_kwh=float(data["heat_demand_kwh"]))
        if data.get("has_heat_pump") and data.get("heat_demand_kwh")
        else None
    )
    return Household(
        postcode4=data["postcode4"],
        annual_consumption_kwh=float(data["annual_consumption_kwh"]),
        # Round one does not ask. False is the dataclass default and also the
        # conservative direction: assuming somebody is home would raise their
        # self-consumption rate and understate the shock.
        daytime_occupancy=bool(data.get("daytime_occupancy", False)),
        ev=ev,
        heat_pump=heat_pump,
    )


def build_pv_system(data: dict[str, Any]) -> PVSystem:
    return PVSystem(
        peak_power_wp=int(data["peak_power_wp"]),
        azimuth_deg=float(data["azimuth_deg"]),
        tilt_deg=float(data["tilt_deg"]),
    )


def build_battery_spec(data: dict[str, Any]) -> BatterySpec | None:
    """The battery this household already owns, if any.

    This is not the battery the advice sizes. That one comes from the capacity
    curve in ampeer_advice.battery and is chosen, not reported.
    """
    if not data.get("has_battery") or not data.get("battery_capacity_kwh"):
        return None
    capacity = float(data["battery_capacity_kwh"])
    power = capacity * BATTERY_C_RATE
    return BatterySpec(capacity_kwh=capacity, max_charge_kw=power, max_discharge_kw=power)


def build_tariffs(data: dict[str, Any]) -> tuple[TariffSet, TariffSet, TariffSet]:
    """Return (baseline, scenario, dynamic_scenario).

    The dynamic scenario is built for every household, including one that
    already has a dynamic contract: the rule that compares them has to be able
    to say that switching back would be better, and it cannot say that from one
    tariff set.
    """
    dynamic_requested = bool(data.get("dynamic_contract", False))
    return (
        baseline_tariffs(),
        scenario_2027_tariffs(dynamic=dynamic_requested),
        scenario_2027_tariffs(dynamic=not dynamic_requested),
    )
```

If `scenario_2027_tariffs` does not accept `dynamic` as shown, read
`ampeer_advice/tariffs.py` and match its real signature. Do not edit that file.

- [ ] **Step 4: Write the failing rendering tests**

`tests/test_advice_rendering.py`:

```python
"""What a reader is finally shown.

Three properties are not negotiable and none of them is a matter of taste:
never a number without a band, the confidence label in plain sight, and the
free routes first. Each has its own test because each would fail silently.
"""

from __future__ import annotations

import json
from decimal import Decimal

from advice.rendering import money, render
from ampeer_advice.types import (
    Advice,
    BatteryAdvice,
    Confidence,
    FiredRule,
    Route,
)
from ampeer_sim.types import Band, ProductionSource, Result

BAND = Band(
    p10_eur=Decimal("561.11"), p50_eur=Decimal("700.08"), p90_eur=Decimal("846.90"), runs=243
)

RESULT = Result(
    engine_version="0.1.0",
    band=BAND,
    self_consumption_rate=0.31,
    production_source=ProductionSource.PVGIS,
    profile_year=2025,
    weather_year=2023,
)

ADVICE = Advice(
    engine_version="0.1.0",
    advice_version="0.1.0",
    confidence=Confidence.INDICATIVE,
    headline=BAND,
    fired=(
        FiredRule(
            rule_id="SHIFT_FLEXIBLE_LOAD",
            route=Route.SHIFT_BEHAVIOUR,
            estimated_saving_eur=Decimal("143.5612"),
        ),
    ),
    routes=(Route.SHIFT_BEHAVIOUR, Route.SMART_CONTROL, Route.STORAGE),
    battery=None,
)


def test_money_is_a_string_with_two_decimals() -> None:
    """JSON has floats and no decimals. A euro amount that goes through a JSON
    float parser is exactly the rounding error this project avoids everywhere
    else, so amounts cross the wire as text."""
    assert money(Decimal("143.5612")) == "143.56"
    assert money(Decimal("700")) == "700.00"
    assert money(Decimal("0")) == "0.00"


def test_money_rounds_half_away_from_zero_everywhere() -> None:
    """One rounding convention, in one function. Two conventions in one
    response is how a total stops matching its own parts."""
    assert money(Decimal("0.125")) == "0.13"
    assert money(Decimal("-0.125")) == "-0.13"


def test_the_headline_is_a_band_and_never_a_single_number() -> None:
    payload = render(ADVICE, RESULT, token="abc123")
    assert set(payload["headline"]) == {"p10", "p50", "p90", "runs"}
    assert payload["headline"]["p50"] == "700.08"
    assert payload["headline"]["runs"] == 243


def test_no_key_anywhere_in_the_response_holds_a_lone_middle_value() -> None:
    """Walks the whole document. A p50 without its neighbours anywhere in here
    is a number presented as certain, which is the one thing this product
    promises not to do."""
    payload = render(ADVICE, RESULT, token="abc123")

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if "p50" in node:
                assert {"p10", "p90"} <= set(node), f"lone p50 in {sorted(node)}"
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)


def test_the_confidence_label_sits_at_the_top_level() -> None:
    """A footnote is where a caveat goes to be ignored."""
    payload = render(ADVICE, RESULT, token="abc123")
    assert payload["confidence"] == "INDICATIVE"


def test_all_three_routes_are_always_present_and_always_in_order() -> None:
    """Two rules at once. The free routes come first even when they are worth
    nothing, and an empty route is sent rather than dropped, so the frontend
    never has to know the order to restore it."""
    payload = render(ADVICE, RESULT, token="abc123")
    assert [route["route"] for route in payload["routes"]] == [
        "SHIFT_BEHAVIOUR",
        "SMART_CONTROL",
        "STORAGE",
    ]
    assert payload["routes"][1]["rules"] == []


def test_every_fired_rule_carries_its_id_and_its_dutch_text() -> None:
    """The id is what makes an advice explainable and reproducible; the text is
    what a person reads. Sending only the text would make the advice
    unauditable, sending only the id would make it unreadable."""
    payload = render(ADVICE, RESULT, token="abc123")
    rule = payload["routes"][0]["rules"][0]
    assert rule["rule_id"] == "SHIFT_FLEXIBLE_LOAD"
    assert rule["saving_eur"] == "143.56"
    assert len(rule["text"]) > 20


def test_a_household_with_no_battery_advice_still_gets_the_key() -> None:
    """An absent key and a null mean different things to a frontend, and only
    one of them is 'we looked and the answer is no'."""
    payload = render(ADVICE, RESULT, token="abc123")
    assert "battery" in payload
    assert payload["battery"] is None


def test_a_battery_advice_reports_a_payback_band_and_a_break_even_price() -> None:
    """'No battery' is a valid and required outcome, and it needs a defensible
    reason attached. The break-even price is that reason."""
    advice = Advice(
        engine_version="0.1.0",
        advice_version="0.1.0",
        confidence=Confidence.GOOD,
        headline=BAND,
        fired=(),
        routes=(Route.SHIFT_BEHAVIOUR, Route.SMART_CONTROL, Route.STORAGE),
        battery=BatteryAdvice(
            sized_capacity_kwh=7.0,
            annual_saving_eur=Decimal("422.31"),
            curve=((3.0, Decimal("210.00")), (7.0, Decimal("422.31"))),
            break_even_cost_per_kwh=Decimal("696.82"),
        ),
    )
    payload = render(advice, RESULT, token="abc123")
    battery = payload["battery"]
    assert battery["sized_capacity_kwh"] == 7.0
    assert battery["break_even_cost_per_kwh"] == "696.82"
    assert battery["annual_saving_eur"] == "422.31"
    assert battery["curve"] == [[3.0, "210.00"], [7.0, "422.31"]]


def test_the_response_names_the_versions_and_years_it_was_computed_with() -> None:
    """Every calculation logs its engine version. An advice that cannot say
    which model produced it cannot be defended when somebody disagrees."""
    payload = render(ADVICE, RESULT, token="abc123")
    assert payload["engine_version"] == "0.1.0"
    assert payload["advice_version"] == "0.1.0"
    assert payload["production_source"] == "PVGIS"
    assert payload["profile_year"] == 2025
    assert payload["weather_year"] == 2023


def test_the_whole_response_survives_json_serialisation() -> None:
    """A Decimal that reached the payload would raise here rather than in
    production."""
    payload = render(ADVICE, RESULT, token="abc123")
    assert json.loads(json.dumps(payload)) == payload
```

`BatteryAdvice` may carry fields beyond the four used above. Read
`ampeer_advice/types.py`, construct it with everything it requires, and render every
field that a reader needs. Do not change that file.

- [ ] **Step 5: Run and watch it fail**

Run: `uv run --no-sync pytest tests/test_advice_rendering.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'advice.rendering'`.

- [ ] **Step 6: Write the rendering**

`backend/advice/rendering.py`:

```python
"""An Advice into the JSON a browser receives.

Money leaves as a string. JSON has floats and no decimals, so an amount that
passes through a JSON number is rounded by whichever parser touches it last,
which is precisely the error the Decimal rule elsewhere in this project exists
to prevent. Rounding therefore happens once, here, in `money`.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ampeer_advice.nl import ROUTE_TITLES, text_for
from ampeer_advice.types import Advice, Route
from ampeer_sim.types import Band, Result

#: Every amount in a response is quantized here and nowhere else. Two rounding
#: conventions in one document is how a total stops matching its own parts.
CENTS = Decimal("0.01")

#: The order a reader sees. The two free routes come first whatever they are
#: worth, and an empty one is still sent, so the frontend never has to know
#: this order in order to restore it.
ROUTE_ORDER: tuple[Route, ...] = (Route.SHIFT_BEHAVIOUR, Route.SMART_CONTROL, Route.STORAGE)


def money(value: Decimal) -> str:
    return str(value.quantize(CENTS, rounding=ROUND_HALF_UP))


def _band(band: Band) -> dict[str, Any]:
    return {
        "p10": money(band.p10_eur),
        "p50": money(band.p50_eur),
        "p90": money(band.p90_eur),
        "runs": band.runs,
    }


def _routes(advice: Advice) -> list[dict[str, Any]]:
    return [
        {
            "route": route.name,
            "title": ROUTE_TITLES[route],
            "rules": [
                {
                    "rule_id": fired.rule_id,
                    "text": text_for(fired.rule_id),
                    "saving_eur": (
                        money(fired.estimated_saving_eur)
                        if fired.estimated_saving_eur is not None
                        else None
                    ),
                }
                for fired in advice.fired
                if fired.route is route
            ],
        }
        for route in ROUTE_ORDER
    ]


def _battery(advice: Advice) -> dict[str, Any] | None:
    if advice.battery is None:
        return None
    battery = advice.battery
    return {
        "sized_capacity_kwh": battery.sized_capacity_kwh,
        "annual_saving_eur": money(battery.annual_saving_eur),
        "break_even_cost_per_kwh": money(battery.break_even_cost_per_kwh),
        "curve": [[capacity, money(saving)] for capacity, saving in battery.curve],
    }


def render(advice: Advice, result: Result, token: str) -> dict[str, Any]:
    return {
        "token": token,
        # Top level, never nested. A caveat in a footnote is a caveat nobody
        # reads.
        "confidence": advice.confidence.name,
        "headline": _band(advice.headline),
        "routes": _routes(advice),
        "battery": _battery(advice),
        "engine_version": advice.engine_version,
        "advice_version": advice.advice_version,
        "production_source": result.production_source.name,
        "profile_year": result.profile_year,
        "weather_year": result.weather_year,
    }
```

`BatteryAdvice` in this repository carries a payback band and a verdict beyond the four
fields shown. Read `ampeer_advice/types.py` and `ampeer_advice/advise.py`, render every
field a reader needs, and make sure `payback_years` is emitted as a band with `p10`,
`p50` and `p90`, never as one figure. The recursive test in Step 4 fails if it is not.

- [ ] **Step 7: Run both test files**

Run: `uv run --no-sync pytest tests/test_advice_assembly.py tests/test_advice_rendering.py -v`
Expected: PASS.

Run: `uv run --no-sync mypy backend/advice/assembly.py backend/advice/rendering.py`
Expected: `Success: no issues found`.

- [ ] **Step 8: Stop. Do not commit.** Report the outputs to the barrier.

---

## Phase 2: the integration gate

### Task 6: The seam, the endpoints, and every gate

This task runs alone, after all four lanes report. It is the only task that runs git.

**Files:**
- Create: `backend/advice/service.py`, `backend/advice/views.py`, `backend/advice/urls.py`, `tests/test_advice_api.py`
- Modify: `backend/ampeer/urls.py`

- [ ] **Step 1: Read all four lanes' output and reconcile the names**

Before writing anything, read `backend/advice/models.py`, `serializers.py`,
`production.py`, `profiles.py`, `assembly.py` and `rendering.py` as they were actually
written. Where a lane's real signature differs from this plan's Interfaces block, the
code is right and the plan is stale: adapt, and note the difference in the commit
message so the plan can be corrected.

- [ ] **Step 2: Write the composition root**

`backend/advice/service.py`:

```python
"""The one place the halves are put together.

Nothing above this file knows what a Household is, and nothing below it knows
what an HTTP request is. That separation is why the simulation core can be
validated without a database and without a server, which matters because it is
the only part of this system where a fault produces a plausible wrong number
rather than an error message.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

from advice.assembly import build_battery_spec, build_household, build_pv_system, build_tariffs
from advice.models import AuditEvent, StoredAdvice
from advice.production import production_provider
from advice.profiles import profile_provider
from advice.rendering import render
from ampeer_advice.advise import advise
from ampeer_sim.simulate import run_advice
from ampeer_sim.timebase import YearGrid


def compute_and_store(data: dict[str, Any], question_count: int) -> dict[str, Any]:
    """Run the engine for one set of answers, store the result, log the event.

    `question_count` is the number of questions the form asked, not the number
    of values it produced. Round one asks four and yields five, because
    orientation and tilt are one question about one roof. Passing the value
    count would push every estimate over the GOOD threshold and delete the
    distinction the confidence label exists to make.
    """
    weather_year = settings.AMPEER_WEATHER_YEAR
    grid = YearGrid.for_year(settings.AMPEER_PROFILE_YEAR)
    profiles = profile_provider()
    production = production_provider(weather_year)

    household = build_household(data)
    system = build_pv_system(data)
    battery_spec = build_battery_spec(data)
    baseline, scenario, dynamic_scenario = build_tariffs(data)

    result = run_advice(
        household=household,
        pv_system=system,
        baseline=baseline,
        scenario=scenario,
        grid=grid,
        profile_provider=profiles,
        production_provider=production,
        battery_spec=battery_spec,
        weather_year=weather_year,
    )
    advice = advise(
        household=household,
        pv_system=system,
        scenario=scenario,
        grid=grid,
        profile_provider=profiles,
        production_provider=production,
        result=result,
        filled_fields=question_count,
        dynamic_contract=bool(data.get("dynamic_contract", False)),
        battery_spec=battery_spec,
        dynamic_scenario=dynamic_scenario,
        weather_year=weather_year,
    )

    stored = StoredAdvice.create(inputs=data, advice={})
    payload = render(advice, result, token=stored.token)
    stored.advice = payload
    stored.save(update_fields=["advice"])

    # Context without a personal detail: the token so the record is findable
    # and the postcode area so a later question about coverage can be answered.
    # No IP address: this log records what the service did, not who visited.
    AuditEvent.record(
        AuditEvent.ADVICE_GENERATED,
        token=stored.token,
        postcode4=data["postcode4"],
        confidence=payload["confidence"],
        engine_version=payload["engine_version"],
        advice_version=payload["advice_version"],
    )
    return payload
```

- [ ] **Step 3: Write the views and the urls**

`backend/advice/views.py`:

```python
"""Three endpoints, anonymous, no cookie, no session.

There is nothing to log in to, so there is nothing to steal from a session and
nothing for a cross-site request to abuse: both POSTs are anonymous and change
nothing that belongs to anyone.
"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from advice.models import StoredAdvice
from advice.serializers import EstimateInputSerializer, RefineInputSerializer
from advice.service import compute_and_store


class _ComputeView(APIView):
    """Shared body of the two POST endpoints."""

    throttle_scope = "advice-compute"
    serializer_class: type[EstimateInputSerializer] = EstimateInputSerializer

    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload: dict[str, Any] = compute_and_store(
            dict(serializer.validated_data), self.serializer_class.QUESTION_COUNT
        )
        return Response(payload, status=status.HTTP_201_CREATED)


class EstimateView(_ComputeView):
    serializer_class = EstimateInputSerializer


class RefineView(_ComputeView):
    serializer_class = RefineInputSerializer


class StoredAdviceView(APIView):
    throttle_scope = "advice-read"

    def get(self, request: Request, token: str) -> Response:
        stored = StoredAdvice.get_live(token)
        if stored is None:
            # An unknown token and an expired one answer identically. Telling a
            # caller that a token used to exist tells them something.
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(stored.advice)
```

`backend/advice/urls.py`:

```python
from __future__ import annotations

from django.urls import path

from advice.views import EstimateView, RefineView, StoredAdviceView

urlpatterns = [
    path("estimate/", EstimateView.as_view(), name="advice-estimate"),
    path("refine/", RefineView.as_view(), name="advice-refine"),
    # 22 url-safe characters from secrets.token_urlsafe(16). The pattern is
    # narrow so a malformed token is a 404 from the router rather than a
    # database query.
    path("<str:token>/", StoredAdviceView.as_view(), name="advice-detail"),
]
```

`backend/ampeer/urls.py` becomes:

```python
"""Root URL configuration."""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, include, path

urlpatterns: list[URLPattern | URLResolver] = [
    path("api/advice/", include("advice.urls")),
]
```

- [ ] **Step 4: Write the endpoint tests**

`tests/test_advice_api.py`:

```python
"""The three endpoints, end to end, against a real database.

These are the only tests that run the whole thing: validation, the engine, the
cache, storage and rendering. The engine is real; only PVGIS is replaced, and
it is replaced by the offline table this project already ships rather than by a
stub, so what these tests exercise is what a visitor gets when PVGIS is down.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from advice.models import AuditEvent, ProductionCache, StoredAdvice

pytestmark = pytest.mark.django_db

ESTIMATE = {
    "postcode4": "5401",
    "peak_power_wp": 3500,
    "azimuth_deg": 0,
    "tilt_deg": 35,
    "annual_consumption_kwh": 3500,
}

REFINE = ESTIMATE | {
    "daytime_occupancy": True,
    "has_ev": False,
    "ev_behaviour": None,
    "has_heat_pump": False,
    "heat_demand_kwh": None,
    "dynamic_contract": False,
    "has_battery": False,
    "battery_capacity_kwh": None,
}


@pytest.fixture(autouse=True)
def _offline_providers(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """No network in tests, and no invented profile either.

    Production comes from the offline yield table, which is real data from nine
    PVGIS years. Consumption comes from a flat fraction series, which is not a
    model of anything and is only acceptable because these tests assert the
    shape of the response and never a euro amount. The calibration and golden
    tests are where the numbers are judged.
    """
    import numpy as np

    from ampeer_sim.production.pvgis import FallbackProvider
    from ampeer_sim.types import ProfileCategory

    class FlatProfiles:
        def fractions(self, year: int, category: ProfileCategory):
            from ampeer_sim.timebase import YearGrid

            quarters = YearGrid.for_year(year).quarters
            return np.full(quarters, 1.0 / quarters)

    monkeypatch.setattr("advice.service.profile_provider", lambda: FlatProfiles())
    monkeypatch.setattr(
        "advice.service.production_provider",
        lambda weather_year: __import__(
            "advice.production", fromlist=["CachedProductionProvider"]
        ).CachedProductionProvider(FallbackProvider(weather_year), weather_year=weather_year),
    )


def test_an_estimate_returns_a_complete_advice() -> None:
    response = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json")
    assert response.status_code == 201, response.data
    payload = response.json()
    assert payload["confidence"] == "INDICATIVE"
    assert set(payload["headline"]) == {"p10", "p50", "p90", "runs"}
    assert [route["route"] for route in payload["routes"]] == [
        "SHIFT_BEHAVIOUR",
        "SMART_CONTROL",
        "STORAGE",
    ]
    assert payload["token"]


def test_a_refine_is_called_good_and_an_estimate_is_not() -> None:
    """Four questions and nine questions must not produce the same label.

    This pins the count that ampeer_advice.confidence reads. Passing the number
    of serializer fields instead of the number of questions would make both of
    these GOOD, and nothing else in the system would notice.
    """
    estimate = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json")
    refine = APIClient().post(reverse("advice-refine"), REFINE, format="json")
    assert estimate.json()["confidence"] == "INDICATIVE"
    assert refine.json()["confidence"] == "GOOD"


def test_a_stored_advice_comes_back_unchanged_through_its_link() -> None:
    created = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json").json()
    fetched = APIClient().get(reverse("advice-detail", args=[created["token"]]))
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_two_requests_get_different_tokens() -> None:
    client = APIClient()
    first = client.post(reverse("advice-estimate"), ESTIMATE, format="json").json()
    second = client.post(reverse("advice-estimate"), ESTIMATE, format="json").json()
    assert first["token"] != second["token"]


def test_an_unknown_token_is_a_404() -> None:
    response = APIClient().get(reverse("advice-detail", args=["A" * 22]))
    assert response.status_code == 404


def test_an_expired_token_is_a_404_and_not_stale_content() -> None:
    created = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json").json()
    StoredAdvice.objects.filter(token=created["token"]).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert APIClient().get(reverse("advice-detail", args=[created["token"]])).status_code == 404


def test_an_invalid_estimate_is_refused_with_the_field_named() -> None:
    response = APIClient().post(
        reverse("advice-estimate"), ESTIMATE | {"postcode4": "540111"}, format="json"
    )
    assert response.status_code == 400
    assert "postcode4" in response.json()


def test_an_unknown_field_is_refused_at_the_endpoint() -> None:
    response = APIClient().post(
        reverse("advice-estimate"), ESTIMATE | {"email": "a@b.nl"}, format="json"
    )
    assert response.status_code == 400


def test_a_second_identical_request_does_not_fetch_production_twice() -> None:
    """Definition of done, proven at the endpoint rather than at the provider."""
    client = APIClient()
    client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    assert ProductionCache.objects.count() == 1
    client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    assert ProductionCache.objects.count() == 1


def test_every_generated_advice_writes_exactly_one_audit_line() -> None:
    APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json")
    assert AuditEvent.objects.filter(event_type="ADVICE_GENERATED").count() == 1


def test_the_audit_line_holds_no_personal_detail() -> None:
    APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json")
    context = AuditEvent.objects.get().context
    assert context["postcode4"] == "5401"
    assert set(context) == {"token", "postcode4", "confidence", "engine_version", "advice_version"}


def test_the_stored_input_holds_only_what_was_asked() -> None:
    created = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json").json()
    stored = StoredAdvice.objects.get(token=created["token"])
    assert set(stored.inputs) == set(ESTIMATE)


def test_the_twenty_first_computation_in_an_hour_is_refused() -> None:
    """Twenty an hour is generous for a real visit and too little to occupy the
    machine. This is the only test that proves the limit is switched on."""
    cache.clear()
    client = APIClient()
    codes = [
        client.post(reverse("advice-estimate"), ESTIMATE, format="json").status_code
        for _ in range(21)
    ]
    assert codes[:20] == [201] * 20, codes
    assert codes[20] == 429


def test_reading_a_link_is_allowed_far_more_often_than_computing_one() -> None:
    cache.clear()
    client = APIClient()
    token = client.post(reverse("advice-estimate"), ESTIMATE, format="json").json()["token"]
    codes = [client.get(reverse("advice-detail", args=[token])).status_code for _ in range(30)]
    assert set(codes) == {200}, "sharing a link must not hit the compute limit"


def test_no_endpoint_sets_a_cookie() -> None:
    """There is no session, so there is nothing to fixate and nothing to steal."""
    client = APIClient()
    response = client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    assert not response.cookies


def test_an_advice_arrives_within_a_second_once_production_is_cached() -> None:
    """Definition of done. The first request pays for the production series;
    every one after it is what a visitor actually experiences."""
    import time

    client = APIClient()
    client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    started = time.perf_counter()
    response = client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    elapsed = time.perf_counter() - started
    assert response.status_code == 201
    assert elapsed < 1.0, f"a cached advice took {elapsed:.3f}s"
```

- [ ] **Step 5: Run the endpoint tests**

Run: `uv run --no-sync pytest tests/test_advice_api.py -v`
Expected: PASS.

If the timing test fails, do not raise the budget. The budget is a promise in the
definition of done. Find what is slow, or report that it cannot be met and why.

- [ ] **Step 6: Run every gate the pipeline runs**

```bash
uv sync --locked --group dev --group backend
uv run ruff check ampeer_sim ampeer_advice backend tests tools
uv run ruff format ampeer_sim ampeer_advice backend tests tools
uv run mypy ampeer_sim ampeer_advice backend tools
uv run pytest --cov --cov-report=term-missing
uv run pre-commit run --all-files --show-diff-on-failure
uv run bandit -c pyproject.toml -r ampeer_sim ampeer_advice backend tools
uv run pip-audit
```

Every one must pass. Coverage must be at or above 98.00 measured at two decimals.

If coverage drops below the floor, **write the missing tests**. Do not lower
`fail_under`, do not widen `omit`, and do not add a `# pragma: no cover`. A floor below
the current level makes a regression invisible, which is the whole reason it is there.

- [ ] **Step 7: Prove the new gates can go red**

Three checks in this repository were decoration in their first version and were only
found by breaking them on purpose. Do the same here and report each result:

1. Change `ROUTE_ORDER` in `rendering.py` to put `STORAGE` first. Run
   `pytest tests/test_advice_rendering.py tests/test_advice_api.py`. Expect FAIL. Revert.
2. Remove `"p10"` from `_band`. Run `pytest tests/test_advice_rendering.py`. Expect FAIL
   from the recursive walk, not only from the explicit headline test. Revert.
3. Change the compute throttle to `"1000/hour"` in `base.py`. Run
   `pytest tests/test_advice_api.py`. Expect FAIL. Revert.
4. Delete the `get_live` expiry filter so it returns any row. Run
   `pytest tests/test_advice_models.py tests/test_advice_api.py`. Expect FAIL. Revert.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: serve advice over HTTP from four answers

Django 5.2 LTS in backend/, three anonymous endpoints, no account and no
cookie. The engine is unchanged and imported, not reimplemented.

Django 5.2 rather than the current 6.1: 6.1 is not an LTS and its support
window closes around April 2027, the quarter net metering ends and this
product is busiest. 5.2 is supported to April 2028.

Synchronous rather than Celery. Measured 2026-08-21: the band costs 0.30s and
the advice 0.23s, so a request with a cached production series stays well
under a second. The threshold for revisiting is recorded in the spec: a p90
response time above two seconds moves the work to a worker.

PVGIS answers are cached in Postgres, keyed by postcode4, whole-degree azimuth
and tilt, and weather year. Whole degrees because a float key misses its own
entry on 35.000000001, and because a rounded lookup against a float key would
return a series computed for a different roof than the simulation assumes.
Rounding happens once, in the serializer.

filled_fields is the number of questions asked, not the number of values
produced. Round one asks four questions and yields five, because orientation
and tilt are one question about one roof. Passing five would push every
estimate past GOOD_FIELD_COUNT and silently delete the distinction the
confidence label exists to make. Pinned by a test on both endpoints.

There is no fallback consumption profile and there must not be one. Every
other external source here degrades to measured data; a consumption shape has
none we may redistribute, so a deployment without the NEDU file refuses to
start rather than answering from an invented curve.

The coverage gate globbed only the repository root, so every Django app under
backend/ would have been unmeasured while the gate stayed green. Widened, and
the omit list is now asserted to hold nothing but the two generated entry
points.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 9: Push and report**

```bash
git push -u origin feat/advice-api
```

Report the commit hash and the coverage figure. Do not open the pull request yet; the
audits run first.

---

## Phase 3: three concurrent audits

Three read-only agents, dispatched together, each with one lens. None of them edits code.
Each returns findings with a file, a line and a concrete failure scenario. Nine of the ten
findings in the previous audit round pointed the same way: they made the advice more
favourable, the shock larger or the battery more attractive, and none of them produced an
error message. Look for that direction first.

### Task 7: Audit lens one, privacy

Read the spec's privacy requirements, `CLAUDE.md`'s privacy section, and every file under
`backend/`. Answer, with evidence:

1. Can any personal detail reach the database? Walk `StoredAdvice.inputs`,
   `StoredAdvice.advice` and `AuditEvent.context` field by field. A four digit postcode is
   the deliberate limit; anything narrower than a neighbourhood is a finding.
2. Can a personal detail reach a log line, an error message or a traceback? Check what a
   DRF validation error echoes back, and what Django logs on a 500 with `DEBUG = False`.
3. Is the ninety day retention actually enforced, or only intended? Trace what happens if
   the cron job never runs, and whether anything notices.
4. Does the token behave as the only access path? Look for any endpoint, filter or
   ordering that lets a caller enumerate stored advices without one.
5. Is anything recorded that identifies a visitor rather than an action? An IP address in
   the audit log would be a finding even though it is conventional.

### Task 8: Audit lens two, is this safe to expose

Read every file under `backend/` and the two workflow files. Answer, with evidence:

1. Can a single request make the server do a lot of work? Every numeric bound in
   `serializers.py`, and what 243 simulations cost at each bound. What does a request body
   of ten megabytes do?
2. Is the rate limit real? What is it keyed on, what happens behind a reverse proxy that
   sets `X-Forwarded-For`, and can a caller reset their own counter?
3. Is there any path where a URL is built from user input? `CLAUDE.md` excludes SSRF
   categorically. Trace `postcode4` all the way into the PVGIS provider and say whether it
   reaches URL construction, and what validates it if it does.
4. Are the production settings actually applied when the service runs? Check
   `wsgi.py`'s default settings module and whether a misconfigured deploy could serve with
   `dev` settings.
5. `zlib.decompress` and `np.load` run on data from the database. Is there any path by
   which a caller controls those bytes? Is `allow_pickle=False` set everywhere?
6. Does any error response distinguish "this token never existed" from "this token
   expired"? Timing counts as well as status code.

### Task 9: Audit lens three, does the boundary hold and is the answer honest

Read `backend/`, `ampeer_sim/`, `ampeer_advice/` and the spec. Answer, with evidence:

1. Is the import boundary a fact or only a test? `tests/test_boundaries.py` parses the
   AST. Is there a runtime path, a lazy import or a string-based import that gets Django
   into the pure packages anyway?
2. Does any Dutch advice sentence exist outside `ampeer_advice/nl.py`? Validation messages
   in `serializers.py` are allowed; an advice sentence is not. State which is which.
3. Can any response show a number without its band? Re-derive the answer independently of
   the recursive test in Task 5, including `battery.payback_years`.
4. Is `filled_fields` correct on both endpoints, and would anything catch it if somebody
   changed the serializer field list?
5. Are there two rounding conventions anywhere in one response? Check that a total and its
   parts are quantized by the same function.
6. Does the advice depend anywhere on a commercial relationship? Nothing in
   `AdviceContext` allows it structurally, but check the API layer has not reintroduced a
   supplier, an installer or a partner price.
7. Every number that reached this code from outside the engine: does it have a source and
   a date beside it? `BATTERY_C_RATE` in `assembly.py` and every bound in
   `serializers.py`. A bound chosen for safety is fine and must say so; a bound presented
   as a fact about households needs a source.

Each audit reports findings only. The barrier decides what to fix, fixes it on the same
branch, re-runs every gate, and only then opens the pull request to `dev`.

---

## Self-review

**Spec coverage.** Section 2, where it lives: Task 1. Section 3, synchronous: Task 6, and
the timing test in Task 6 Step 4. Section 4, the PVGIS cache: Task 4. Section 5, storage
and the purge command: Task 2. Section 6, the endpoints and the response shape: Tasks 3, 5
and 6. Section 7, rate limiting: Task 1 sets the rates, Task 6 proves them. Section 8,
audit log: Task 2. Section 9, settings and security: Task 1 and Task 8's audit. Section 10,
Postgres in CI: Task 1 Step 7. Section 11, all eight test regimes: regime 1 in Task 6,
2 in Task 3, 3 in Tasks 2 and 6, 4 in Tasks 2 and 6, 5 in Tasks 4 and 6, 6 in Task 6, 7 in
Tasks 2 and 6, 8 in Task 1. Section 12, all six definition-of-done items: covered by named
tests in Tasks 1, 4 and 6.

**Two things the spec did not settle** and this plan does, both recorded above with their
reasoning: `filled_fields` counts questions and not values, and the roof angles are
rounded once in the serializer.

**One thing neither settles, and it is Stijn's.** `backend/advice/profiles.py` refuses to
start without the NEDU profile file. That file is gitignored because its redistribution
terms are unconfirmed, so **the API cannot be deployed publicly until the licensing
question with NEDU and `energiedatawijzer@hetnormo.nl` is answered.** This plan makes that
a visible deployment blocker rather than hiding it behind an invented profile shape, which
is the only honest option, but it does not remove the blocker. Deelproject 2 will hit it.

**Type consistency.** `QUESTION_COUNT` is the same name in Tasks 3 and 6.
`CachedProductionProvider(inner, weather_year=...)` is constructed identically in Tasks 4
and 6. `render(advice, result, token=...)` matches between Tasks 5 and 6.
`StoredAdvice.create(inputs=, advice=)` and `AuditEvent.record(event_type, **context)`
match between Tasks 2 and 6. `build_tariffs` returns the same three-tuple in Tasks 5 and 6.

**Known stale risk.** Three lanes call into code this plan quotes from memory of the
existing packages: `scenario_2027_tariffs`'s keyword, `PvgisProvider`'s constructor, and
`BatteryAdvice`'s full field list. Each of those steps tells the agent to read the real
file, match it, and stop rather than edit it. That is rule 6, and it is there because the
previous plan's one failure was a lane that could not proceed without touching a file it
did not own.
