"""DB-DBG temporary query-tracing middleware.

Logs every database query per request with timing and a summary.
Enable by setting DB_DEBUG=1 in the environment (Railway or .env).
All log lines are prefixed with "DB-DBG" for easy filtering:

    grep 'DB-DBG' railway-logs.txt
    grep -n 'DB-DBG\|db_debug_middleware' breaking_news/settings.py

To remove permanently when done:
  1. Delete this file.
  2. Remove the 'breaking_news.db_debug_middleware.DbDebugMiddleware' entry
     from MIDDLEWARE in settings.py.
  3. Remove the 'db_debug' logger block from LOGGING in settings.py.
"""

import logging
import os
import re
import time

from django.db import connection

logger = logging.getLogger("db_debug")

# Matches the first meaningful word and the first quoted table/model name in SQL.
_SQL_SUMMARY_RE = re.compile(
    r"^\s*(?P<op>\w+).*?(?:FROM|INTO|UPDATE|TABLE)\s+[\"']?(?P<table>[\w]+)",
    re.IGNORECASE | re.DOTALL,
)

# Paths that generate high-frequency background traffic -- logged at a lower
# verbosity so they don't drown out the interesting commands.
_NOISY_PATHS = {"/messages/poll/", "/connections/status/"}


def _summarise_sql(sql: str) -> str:
    """Return a short human-readable label for a SQL statement."""
    sql_flat = sql.replace("\n", " ").strip()
    m = _SQL_SUMMARY_RE.match(sql_flat)
    if m:
        return f"{m.group('op').upper()} {m.group('table')}"
    # Fallback: first 80 chars
    return sql_flat[:80]


class DbDebugMiddleware:
    """Temporary DB query tracer. Enabled when DB_DEBUG=1 env var is set."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not os.environ.get("DB_DEBUG"):
            return self.get_response(request)

        queries: list[tuple[str, float]] = []

        def _capture(execute, sql, params, many, context):
            t0 = time.monotonic()
            try:
                return execute(sql, params, many, context)
            finally:
                queries.append((sql, (time.monotonic() - t0) * 1000))

        label = f"{request.method} {request.path}"
        noisy = request.path in _NOISY_PATHS

        t_req = time.monotonic()
        with connection.execute_wrapper(_capture):
            response = self.get_response(request)
        req_ms = (time.monotonic() - t_req) * 1000

        if noisy and not queries:
            logger.debug("DB-DBG [%s] CACHED  req=%.1fms", label, req_ms)
            return response

        for i, (sql, ms) in enumerate(queries, 1):
            logger.debug("DB-DBG [%s] Q%d %s %.1fms", label, i, _summarise_sql(sql), ms)

        db_ms = sum(ms for _, ms in queries)
        logger.debug(
            "DB-DBG [%s] TOTAL %d quer%s  db=%.1fms  req=%.1fms",
            label,
            len(queries),
            "y" if len(queries) == 1 else "ies",
            db_ms,
            req_ms,
        )

        return response
