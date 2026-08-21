# Setting up and running the Ampeer stack

This is the file to open first. It says what has to exist on the host before a
deploy can work, what a deploy does, and which four things nothing in this
repository can check for you.

Written in English like every other file under `infra/`. The Dutch/English split
in `CLAUDE.md` is about what a visitor reads; this is operator documentation for
the repository, in the same language as the comments in the files it describes.

Everything here is about the LXC on Proxmox. Nothing in this repository can
create it, register a runner on it, or install a systemd unit, and no task in
this subproject has touched it.

---

## What runs

Four services, in `docker-compose.yml`:

| Service | Image | What it does |
|---|---|---|
| `db` | `postgres:16-alpine`, by digest | The database, on a named volume that survives `down` |
| `api` | `ghcr.io/stijnvandepol/ampeer-api:<tag>` | Django on gunicorn, uid 10001, no port of its own |
| `web` | `ghcr.io/stijnvandepol/ampeer-web:<tag>` | nginx: the exported site, and `/api/` to `api` |
| `tunnel` | `cloudflare/cloudflared`, by digest | The outbound connection Cloudflare answers on |

**Nothing listens.** There is no `ports:` entry anywhere in
`docker-compose.yml`, no host networking and no inbound firewall rule; the
tunnel connector dials out. `tests/test_infra.py` reads the file for a
published port on every pull request, in three different spellings, because
that is a line somebody adds while debugging and does not take out again.

The two images built from this repository are pulled at the release tag in
`AMPEER_VERSION`. A rollback is that one string plus `docker compose up -d`.

---

## 1. The environment file

Copy `infra/.env.example` to **`/srv/ampeer/.env`** on the host and fill it in.
It is outside git on purpose and there is no default for anything in it: a
default for a secret is a secret in the repository with extra steps.

`prod.py` refuses to start without these nine, and gives none of them a value:

| Name | What goes in it |
|---|---|
| `DJANGO_SECRET_KEY` | A fresh signing key. Never a value that has been in a repository |
| `DJANGO_ALLOWED_HOSTS` | Comma separated hostnames, e.g. `ampeer.nl` |
| `DJANGO_CORS_ALLOWED_ORIGINS` | The site's own https origin. Same origin here, so no wildcard and no second host |
| `DJANGO_NUM_PROXIES` | `2` on this host: the tunnel connector and nginx. See the warning below |
| `AMPEER_NEDU_PROFILE_PATH` | Absolute path **on the host** to the NEDU profile file |
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_HOST` | `db`, the compose service name |

Two more names are read by `docker-compose.yml` and are not in that list because
`prod.py` never sees them:

| Name | What goes in it |
|---|---|
| `AMPEER_VERSION` | The release tag both images are pulled at. The deploy job exports it from the tag it is deploying, and a shell variable beats the file, so this only matters when starting the stack by hand |
| `CLOUDFLARE_TUNNEL_TOKEN` | The connector token. It is a credential: anyone who can read this file can run a connector for this tunnel |

The file must be readable only by the account that runs the stack, and it must
have **Unix line endings**. A file edited on Windows arrives with a carriage
return at the end of every value, so `POSTGRES_HOST` becomes `db\r` and the
failure reads as DNS. The preflight refuses such a file rather than trimming it,
because trimming would make the check agree while compose still reads the values
with the carriage return in them.

**`DJANGO_NUM_PROXIES` is a property of the chain, not a preference.** It is how
many proxies of this deployment append to `X-Forwarded-For`, counted from the
right. Set it too high and DRF reads an entry the caller supplied, which means
the rate limit can be reset with one header. Measured on 2026-08-21 against this
stack: with the correct count, 130 requests carrying 130 different forged
`X-Forwarded-For` values produced 120 answers and then ten `429`s. With the
count one too high, the same 130 requests produced 130 answers and no `429` at
all. Two is right for the host because there are two hops; the local test
override uses one because it has no tunnel.

**Verify:**

```sh
bash /srv/ampeer/preflight_env.sh /srv/ampeer/.env
```

It names every missing variable at once, never prints a value, and exits
non-zero if anything is missing. The deploy job runs the same script before it
touches a container.

---

## 2. The consumption profile: a readable file, not a directory

`AMPEER_NEDU_PROFILE_PATH` is the path **on the host**. `docker-compose.yml`
bind mounts it read-only to `/srv/profiles/nedu.csv` inside the api container,
which is the fixed path Django reads.

**It must be an existing, readable file.** If that path does not exist, the
Docker daemon creates an **empty directory** there and mounts the directory over
the place the CSV should be. Nothing complains: the variable is set, the
container starts, the process is alive, and every single advice fails. That is
why two separate things check it and both check for a file rather than for
existence:

- `scripts/preflight_env.sh` refuses a path that is not a file, is not readable,
  or has no `/` in it (compose reads a source with no slash as a *volume name*,
  creates it empty, and mounts that)
- the api image's `HEALTHCHECK` calls `profile_provider()`, which uses
  `Path.is_file()` and not `Path.exists()`, so a directory makes the container
  unhealthy rather than quietly broken

**Verify:**

```sh
ls -l "$(grep '^AMPEER_NEDU_PROFILE_PATH=' /srv/ampeer/.env | cut -d= -f2-)"
docker inspect -f '{{.State.Health.Status}}' ampeer-api-1
```

The first must show a regular file. The second must say `healthy`.

---

## 3. The retention timer is installed by hand

`infra/systemd/ampeer-purge.service` and `infra/systemd/ampeer-purge.timer`
delete advices past their ninety days. **Nothing in this repository installs,
enables or starts them.** No workflow copies them and no test touches them.

```sh
cp infra/systemd/ampeer-purge.* /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ampeer-purge.timer
```

**Verify:**

```sh
systemctl list-timers ampeer-purge.timer     # NEXT must be within a day
systemctl status ampeer-purge.service        # after it has fired once
```

### What notices when the purge stops, and what does not

`purge_expired_advice --check` exits non-zero as soon as a row is more than one
day past its `expires_at`. It deletes nothing, because a check that repairs what
it measures can never report a problem. It runs in exactly two places:

1. **`ExecStartPost=` on the purge unit.** It runs only after a purge succeeded,
   so it asks the question that is left: is anything still overdue? If it is,
   the delete did not do what its own output claimed, and the unit goes to
   `failed` instead of printing a count nobody reads.
2. **A step in the deploy job, after `migrate`.** A deploy that goes green while
   nothing is being deleted is a green tick covering a broken promise.

It is deliberately **not** the container healthcheck, which is what the design
originally said. The readiness check runs every thirty seconds and issues no
database query on purpose; a check that counts rows that often is a load
generator with a nice name.

**Neither of those two catches the case that matters most: a timer that was
never enabled.** `ExecStartPost=` only runs when the unit runs, and the unit
does not run. The deploy step finds nothing until some row is ninety-one days
old, so for the first three months of the service it is silent too. And with the
timer off, the only thing anybody can observe is a link returning 404 after
ninety days, which is exactly what correct looks like.

The only thing that answers that question is:

```sh
systemctl list-timers ampeer-purge.timer
```

and nothing in this repository can run it. That gap is written down here rather
than papered over, because monitoring is explicitly out of scope for this
subproject (section 1 of the design), and a check that appeared to cover this
and did not would be the same shape of false comfort this project keeps finding.

---

## 4. The preflight lives on the host, and the deploy checks that it is current

`scripts/preflight_env.sh` is copied to `/srv/ampeer/preflight_env.sh` by hand,
next to `docker-compose.yml` and `.env`. The deploy job has no checkout, so the
copy it runs is whatever was left there.

That was a silent failure until 2026-08-21: change the script, tag a release,
and the deploy runs the old copy, which still exits zero, so the deploy is green
and the check that was just added is not running.

The deploy therefore compares the sha256 of the copy on the host against a
literal in `.github/workflows/deploy.yml`, before it uses it. A digest and not a
version string, because a version string is only updated by whoever remembered
to update the copy, which is the thing they forgot. `tests/test_stack_smoke.py`
recomputes the digest from the script on every pull request, so the literal
cannot drift from the repository; it can only disagree with the host.

**Whenever `scripts/preflight_env.sh` changes, copy it to the host again** or
the next deploy stops with:

```
the preflight on the host is not the one from this release
  on the host: c0dae0d5...
  this release: afea38d6...
copy scripts/preflight_env.sh from this tag to /srv/ampeer/ and redeploy
```

**Verify:**

```sh
sha256sum /srv/ampeer/preflight_env.sh
grep PREFLIGHT_SHA256 .github/workflows/deploy.yml
```

Also on the host: `docker-compose.yml` itself. It is copied by hand for the same
reason and there is no equivalent check on it, because the deploy reads it as
its own input rather than after it. If it is stale, the deploy runs the stale
one. That is a known limit, not a solved problem.

---

## 5. What a deploy does

A tag matching `v*` on `main` triggers `.github/workflows/deploy.yml`:

- `build` on a GitHub-hosted runner: exports the site with
  `NEXT_PUBLIC_API_BASE=` (empty, so the client uses relative paths), builds
  both images and pushes them to GHCR
- `deploy` on the self-hosted runner, behind `environment: production`: checks
  the preflight's digest, runs the preflight, logs in to GHCR, `pull`, `up -d`,
  `migrate`, `purge_expired_advice --check`, `docker logout`

No checkout, no `docker build`, no token that can read the repository, and
nothing on the host that is not one of those commands.

---

## 6. Logs

Everything writes to stdout and stderr; nothing writes a file inside a
container. There is no `logrotate` configuration because there is nothing to
rotate, so the retention is set on Docker's log driver, per service in
`docker-compose.yml`: `max-size: 10m`, `max-file: 5`. That is 50 MB per service
and 200 MB for the stack, and it is a ceiling rather than a number of days.
Without it, the default `json-file` driver keeps every line until the container
is removed, and `restart: unless-stopped` means the container is not removed.

What is deliberately not in those logs:

- **The token.** nginx maps both `/api/advice/<token>/` and `/advies/<token>/`
  to a route label before writing them, and the error log is raised to `crit`
  in both locations, because at `error` level nginx writes the failing request
  line and two request lines on this site carry a token
- **The visitor's address.** The `privacy` log format has no `$remote_addr`, no
  `$http_x_forwarded_for` and no `$http_referer`. The referer is the one that
  looks harmless: on the advice page it is `/advies/<token>/` for every asset
  that page loads
- **gunicorn's access log**, which is switched off for the same reason

**Verify** (against a running stack, with a token you made yourself):

```sh
docker logs ampeer-web-1 2>/dev/null | grep -E '/(api/advice|advies)/[A-Za-z0-9_-]{22}'
docker logs ampeer-web-1 2>&1 1>/dev/null | grep -E '[A-Za-z0-9_-]{22}'
```

Both must find nothing. Check stderr separately from stdout: the error log is
where this leaked before it was fixed.

---

## 7. Running the stack locally

`infra/compose.test.yml` is an override that swaps the tunnel for a port on
`127.0.0.1` and mounts a synthetic profile. **It must never be used on a host.**
Read its header before using it.

```sh
uv run python tests/test_stack_smoke.py          # writes the two git-ignored fixtures
cd frontend && NEXT_PUBLIC_API_BASE= pnpm build  # the web image copies out/ in
cd ..
docker compose -f infra/docker-compose.yml -f infra/compose.test.yml \
  --env-file infra/fixtures/env.smoke build
docker compose -f infra/docker-compose.yml -f infra/compose.test.yml \
  --env-file infra/fixtures/env.smoke up -d
docker compose -f infra/docker-compose.yml -f infra/compose.test.yml \
  --env-file infra/fixtures/env.smoke run --rm api python backend/manage.py migrate --noinput
```

The site is then on `http://127.0.0.1:8080/`. The `NEXT_PUBLIC_API_BASE=` on the
build is not optional: `api.ts` falls back to `http://127.0.0.1:8000` when the
variable is absent, so an export built without it ships a client that asks the
visitor's own machine for every advice. `web.Dockerfile` greps the built site
for that string and fails the build, so this is a red build rather than a page
that renders perfectly and does nothing.

The profile mounted there is a flat synthetic curve. It proves the bind mount,
the readiness check and the request path work, and the numbers it produces are
arithmetic on a shape nobody measured. It is not an advice and nobody reads it.

Tear down with:

```sh
docker compose -f infra/docker-compose.yml -f infra/compose.test.yml \
  --env-file infra/fixtures/env.smoke down -v
```

---

## The two decisions that are not in this repository

Both are Stijn's, both are written down here so they are a decision and not an
oversight, and neither can be closed by anything in `infra/`.

### The runner `web2` is not ephemeral

Measured on 2026-08-21: `web2` is online with `ephemeral=false`. A non-ephemeral
runner keeps its working directory between jobs, so whatever one job leaves
behind is there for the next one. That is the property that turns a single
compromised job into a permanent foothold, and it is why the deploy job ends
with `docker logout` under `if: always()`.

`tests/test_pipeline_contract.py` refuses every job that says `self-hosted`,
because `ci.yml` and `security.yml` trigger on push to `feat/**` where no
ruleset applies. The deploy job is the single named exception, and it is only
defensible because it triggers on a tag, declares `environment: production`,
checks nothing out and builds nothing. The exception list is asserted to hold
exactly one job.

**The decision:** re-register `web2` as ephemeral, or leave it and accept that
the deploy is less contained than it is written to be. Nothing here can do it,
and no task in this subproject has touched the runner.

### The NEDU redistribution terms are unconfirmed

`AMPEER_NEDU_PROFILE_PATH` points at a file this project does not ship and may
not ship. `advice/profiles.py` refuses to start without it and there is
deliberately no fallback shape: an invented consumption curve would put a made
up number at the centre of every answer while every test stayed green. That is
worse service and better honesty.

The consequence is concrete. **The stack runs on Stijn's own machine with his
own copy, and it cannot go public until the redistribution terms of the NEDU
standard profiles are confirmed.** `data/` is excluded from every build context
by `.dockerignore` for this reason, and `tests/test_stack_smoke.py` fails if
anything re-includes it, because both images are published to a public registry.

**The decision:** confirm the terms, or find a profile that may be
redistributed. Until then this is a deploy that works and may not be pointed at
`ampeer.nl`.

---

## The seven checks

Section 12 of `docs/superpowers/specs/2026-08-21-deploy-design.md` lists seven
things to prove against a running stack. They were run on 2026-08-21 against the
override above and their output is in the commit that added this file. Six of
the seven pass as written.

The first does not, and cannot: it asks for all four services up and healthy,
and the override that makes a local run possible at all is the one that stops
the tunnel from starting. A connector needs a real credential and would register
a route to a tunnel serving a real domain, which is a change to a host. So three
of four come up healthy locally, the fourth is present in the merged document
and deliberately not started, and the tunnel is only ever exercised on the host.
