"""The table the production cache backend uses.

Django ships `createcachetable` as a management command, which makes creating
this table a step in a deploy runbook, and a step in a runbook is a step that a
deploy eventually skips. It is here instead, so the same command that applies
every other schema change applies this one.

What it holds is the rate limit counter and nothing else. Without it prod.py
falls back to Django's LocMemCache, and a throttle counter in a per-process
dict is a limit per worker that resets on every deploy and drops a third of its
entries at random once four hundred distinct clients have been seen.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps: Any, schema_editor: Any) -> None:
    """Create the cache table by name, on this migration's own connection.

    Named explicitly rather than read from CACHES, because `createcachetable`
    with no arguments creates a table only for a cache backend that is a
    DatabaseCache. Under dev and test settings the default cache is in memory,
    so with no argument this migration would quietly do nothing there and the
    statement it runs in production would be one no test has ever executed.
    """
    call_command(
        "createcachetable",
        settings.AMPEER_CACHE_TABLE,
        database=schema_editor.connection.alias,
        verbosity=0,
    )


def drop_cache_table(apps: Any, schema_editor: Any) -> None:
    """The reverse. The table holds nothing but throttle counters, so dropping
    it loses a partial hour of rate limit history and nothing else."""
    schema_editor.execute(
        f"DROP TABLE IF EXISTS {schema_editor.quote_name(settings.AMPEER_CACHE_TABLE)}"
    )


class Migration(migrations.Migration):
    dependencies = [("advice", "0001_initial")]

    operations = [migrations.RunPython(create_cache_table, drop_cache_table)]
