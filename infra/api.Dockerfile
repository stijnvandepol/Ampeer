# The API image. Two stages: dependencies resolved from the lockfile in the
# first, nothing but the virtualenv and the source in the second.
#
# Both stages are pinned by digest, resolved on 2026-08-21 with
# `docker buildx imagetools inspect`. A tag is a name somebody else can
# repoint, and this file decides what runs in production. Re-resolve when
# bumping and write down what you got.
FROM python:3.14-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS build

# uv itself is pinned by digest too, for the same reason, and the tag it
# resolved from is the version .github/workflows/ci.yml pins in setup-uv.
COPY --from=ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1 /uv /usr/local/bin/uv

WORKDIR /app
# UV_PYTHON and UV_PYTHON_DOWNLOADS are load bearing, not tidiness: they make
# uv use the interpreter this image already has and never fetch one. Left to
# itself uv downloads a managed CPython into the build stage's home directory
# and points .venv/pyvenv.cfg at it. The second stage does not have that
# directory, so every process in the final image would fail to start on a path
# that exists only in a layer that was thrown away.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
# --locked, the same flag the pipeline uses. Without it this image resolves its
# own dependency set and stops being the thing that was tested.
#
# --no-install-project because the source is not here yet and does not need to
# be: ampeer_sim and ampeer_advice are pure Python and are put on the path in
# the next stage, so this layer is the third-party set alone and is rebuilt
# only when the lockfile changes.
RUN uv sync --locked --no-dev --group backend --no-install-project

FROM python:3.14-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f

WORKDIR /app
# Not root. A container that runs as uid 0 is one container escape away from
# being the host, and nothing here needs to write anywhere.
#
# --create-home is not decoration. gunicorn 26 starts a control server that
# writes under $HOME, and a system account without a home directory made every
# boot log `Control server error: [Errno 13] Permission denied: '/home/ampeer'`.
# It served anyway, which is the problem: an error on every start is how a log
# stops being read.
RUN useradd --system --uid 10001 --create-home ampeer

COPY --from=build /app/.venv /app/.venv
COPY ampeer_sim ampeer_sim
COPY ampeer_advice ampeer_advice
COPY backend backend
COPY --chmod=0555 infra/entrypoint-api.sh /usr/local/bin/entrypoint-api.sh

# PYTHONPATH names both roots explicitly rather than relying on the working
# directory ending up on sys.path: gunicorn and `python -c` each put the
# current directory there by their own rules, and `docker compose run` changes
# which directory that is.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app:/app/backend" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=ampeer.settings.prod

# The repository root, not backend/. PYTHONPATH names both roots above, so this
# decides nothing about imports and everything about what a command looks like.
#
# Every call site in this repository writes `python backend/manage.py`, and
# backend/manage.py says so in its own header. Making /app the working
# directory means the command inside the container is the command outside it,
# so a person reading the systemd unit, the deploy workflow or the README types
# the same thing everywhere. With /app/backend the two lanes that wrote those
# callers both produced `backend/manage.py`, which resolved to
# /app/backend/backend/manage.py and would have failed on the first deploy and
# on the first purge, in a container nobody was watching.
WORKDIR /app

USER ampeer
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint-api.sh"]

# The image knows how to check itself, so the check lives here rather than only
# in a compose file that can be copied without it.
#
# Three things in this line were found by running it rather than by reading it:
#
# 1. The route is /api/advice/health/. The root URLconf mounts advice.urls at
#    api/advice/, so /api/health/ is a 404.
# 2. prod.py sets SECURE_SSL_REDIRECT, so a plain http request to the loopback
#    is answered with 301 to https://127.0.0.1/..., and a checker that follows
#    it dies on the TLS handshake against a plain http socket. The header is
#    what nginx sends for a real visitor, so this asks the same question a
#    visitor's request does instead of a question only the healthcheck asks.
# 3. The Host header has to be a host this service answers on, and 127.0.0.1
#    is not one. Django validates Host against ALLOWED_HOSTS before any view
#    runs, and prod.py builds that list from DJANGO_ALLOWED_HOSTS, which the
#    README and .env.example both tell the operator to fill with `ampeer.nl`.
#    Measured on 2026-08-21 with DJANGO_ALLOWED_HOSTS=ampeer.nl and a check
#    sending `Host: 127.0.0.1:8000`: every probe returned
#    `urllib.error.HTTPError: HTTP Error 400: Bad Request`, the container read
#    `Up About a minute (unhealthy)` and stayed that way, while a POST to
#    /api/advice/estimate/ carrying `Host: ampeer.nl` answered 201 with a
#    token. A permanently red check is worse than no check: this is the only
#    thing that notices a NEDU mount that is a directory, `depends_on:
#    service_healthy` could never release on it, and infra/README.md tells the
#    operator to expect `healthy`. The check now reads the same variable
#    Django does and sends the first name in it. A leading dot is Django's
#    subdomain pattern and `.ampeer.nl` matches `ampeer.nl`, so it is stripped;
#    `*` matches everything, so the loopback is used for it.
#
# It opens the consumption profile, which is the part a bad mount breaks and
# the part nothing else notices, and it issues no database query.
#
# --start-interval is load bearing rather than tidiness. docker-compose.yml now
# has `web` wait for this check to pass, so the time between container start
# and the first probe is time added to every deploy while nothing is serving.
# The engine's default is five seconds; two makes the wait about as long as the
# gunicorn boot it is waiting for. Anything this check can catch it catches on
# the first probe, so a shorter interval costs nothing and buys the difference.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --start-interval=2s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request as u; hosts=[h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS','').split(',') if h.strip()]; host=hosts[0] if hosts else '127.0.0.1'; host='127.0.0.1' if host=='*' else host.lstrip('.'); u.urlopen(u.Request('http://127.0.0.1:8000/api/advice/health/', headers={'Host': host, 'X-Forwarded-Proto': 'https'}), timeout=4).read()"]
