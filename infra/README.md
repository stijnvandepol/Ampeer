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
| `DJANGO_ALLOWED_HOSTS` | Comma separated hostnames, e.g. `ampeer.nl`. **The first name is load bearing**, see below |
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

**The first name in `DJANGO_ALLOWED_HOSTS` is the one the api container asks
itself about.** Django refuses any request whose `Host` header is not in that
list, before any view runs, and the api image's readiness check has to send a
`Host` header like any other caller. It reads this variable and sends the first
name in it, so the list has to begin with a name this service really answers on,
which on this host is `ampeer.nl`.

This was a live defect until 2026-08-21. The check sent a hardcoded
`Host: 127.0.0.1:8000`, which is not in the list this file tells you to write.
Measured with `DJANGO_ALLOWED_HOSTS=ampeer.nl`: every probe returned
`HTTP Error 400: Bad Request`, `docker ps` read `Up About a minute (unhealthy)`
and never changed, while a `POST /api/advice/estimate/` carrying
`Host: ampeer.nl` answered `201` at the same moment. The service worked and the
container was red forever, which is the worst of both: section 2 below tells you
to expect `healthy`, this check is the only thing that notices a NEDU profile
mounted as a directory, and `web` waits on it before it starts.

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
docker inspect -f '{{json .State.Health.Log}}' ampeer-api-1
```

The first must show a regular file. The second must say `healthy`. The third is
what to read when it does not, and it distinguishes the two failures that used
to look the same: `HTTP Error 503: Service Unavailable` is this section's
failure, a profile that is not a readable file, measured against a stack with a
directory mounted in its place on 2026-08-21. `HTTP Error 400: Bad Request` is
not about the profile at all; it means the check's `Host` header is not in
`DJANGO_ALLOWED_HOSTS`, so read section 1.

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

### What the ninety days actually promise

`DELETE` in PostgreSQL marks a row dead; it does not overwrite it. The bytes stay
in the table's heap until an autovacuum reuses that space, and a copy of them
stays in the write-ahead log for as long as the WAL segments that carry the
delete are kept. Nothing in this stack shortens either, and the volume
`ampeer-db` is not touched by the purge at all.

So the promise the purge keeps is: **ninety days after an advice is made, the
service stops returning it and stops being able to find it.** That is the
promise a link, an export request and a subject access request are all about,
and it is the one worth making. It is not a promise that the household's figures
have left the disk at the moment the timer fires, and the volume is not evidence
either way.

Anything stronger than that is a different mechanism, not a shorter timer: it
means `VACUUM FULL` or a rewrite of the table, a bounded WAL retention, and a
statement about the backup that the previous paragraph in section 7 says nobody
is taking. None of it is here, and claiming the weaker thing accurately is worth
more than implying the stronger one.

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

### What `up -d` does and does not catch

`web` waits for the api container's own healthcheck (`depends_on: condition:
service_healthy`), not merely for it to have started. That is the difference
between a deploy that goes red at the step somebody is watching and a deploy
that goes green on a broken image. Measured on 2026-08-21 with an api image
that starts and immediately exits:

| | `service_started` | `service_healthy` |
|---|---|---|
| `up -d` exit code | `0` | `1`, `dependency failed to start: container ampeer-api-1 is unhealthy` |
| api container | `Restarting (1)` | `Restarting (1)` |
| first red step | `migrate`, two steps later | `up -d` itself |

It costs about ninety seconds to go red on a broken image, which is the api
healthcheck's twenty second start period plus three failed probes, and it costs
availability on a good one. Measured over a probe every 0.23 seconds across a
release that changes both image tags: the window in which nothing served went
from **0.74 s** to **3.29 s**, because `web` now starts after the api's first
successful probe instead of immediately.

**It is not a rollback.** By the time `up -d` reports the failure the previous
api container has already been destroyed, because compose recreates rather than
starts a second one. The only way back is to set `AMPEER_VERSION` in
`/srv/ampeer/.env` to the previous tag and run `up -d` by hand. Nothing in this
repository does that automatically and nothing here can.

### Every deploy is a short outage, and `migrate` runs after traffic

Two facts, both measured on 2026-08-21 against a real stack, both properties of
running one container per service:

- **There is no second instance.** compose stops `web` and starts it again, so
  between those two moments the site serves nothing at all. With the deploy's
  own command, `up -d --remove-orphans` on a release that changes both tags,
  that gap was 3.29 seconds and four consecutive connection refusals. With
  `up -d --force-recreate`, which the deploy does **not** use, the database is
  recreated too and the gap was 11.62 seconds over eight refusals.
- **`migrate` runs after the new API is already answering.** `/api/advice/health/`
  returned `200` the moment `up -d` returned, and the `migrate` step took a
  further 3.27 seconds with nothing to apply. A release that adds a column and
  reads it therefore serves errors for the length of a `docker compose run`.

Neither is fixable from `infra/`. The first needs a second instance behind
something that can move traffic, which this deployment does not have; the second
needs the deploy job to migrate before it switches, which is
`.github/workflows/deploy.yml`. Both are written down here rather than left to
be discovered during a release.

### `web` cannot start while `api` does not resolve

nginx resolves every upstream name while it parses its configuration, so a
container whose configuration says `proxy_pass http://api:8000` refuses to start
at all while the name `api` does not resolve. Docker removes a stopped
container's name from the network's DNS, so this is not hypothetical.

Measured on 2026-08-21 against a running stack: stop `api`, restart `web`, and
`web` crash-loops on

```
nginx: [emerg] host not found in upstream "api" in /etc/nginx/nginx.conf
```

with the site returning nothing at all rather than a page. The same thing
happens on its own whenever the api image is broken: an api container in a
restart loop takes the statically exported site down with it, and that site
needs no API and no database to render.

`depends_on` protects the ordering during `up`, and it is the wrong tool for a
reboot: Docker's restart policy starts containers in no particular order, so on
a host reboot `web` may come up first, fail, and be restarted by the policy with
a backoff that grows to a minute. It recovers if `api` eventually comes up. If
`api` never does, because the database cannot initialise, the site stays dark
for a reason that has nothing to do with the pages.

**The fix is one directive and one variable in `infra/nginx/nginx.conf`:** a
`resolver 127.0.0.11 valid=10s;` and a `proxy_pass` whose upstream is a variable
rather than a literal name, which defers the lookup to request time. nginx then
starts with the api absent and answers 502 for `/api/` while serving every page.
Until that lands, this coupling is real and this is where it is written down.

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

The containers are called `ampeer-local-api-1`, `ampeer-local-web-1` and
`ampeer-local-db-1`, not `ampeer-api-1`. That is the override's `name:` line and
it is the next paragraph's whole subject; where a verify step elsewhere in this
file names `ampeer-web-1`, locally it is `ampeer-local-web-1`.

### `down -v` deletes a database, and the project name decides which one

`-v` removes named volumes, and the only named volume in this stack is the one
holding every stored advice. Until 2026-08-21 the commands above ran under the
project name `ampeer`, which is the name the host uses, because
`docker-compose.yml` sets it and compose takes the project name from the last
file that names one. Typed in a checkout on a machine whose docker context points
at the LXC, the teardown below would have destroyed the production database.
Nothing in this repository backs that database up or mentions a backup.

`infra/compose.test.yml` now sets `name: ampeer-local`, so every command that
includes it names the local project and the production one cannot be reached by
any of them. `tests/test_stack_smoke.py` asserts that the two names differ, and
that no code block in this file prints `down -v` without the override in the
same block.

That is a fix for the local commands, not for the two words. On the host,
`docker compose -f /srv/ampeer/docker-compose.yml ... down -v` still deletes the
database, because that is the production teardown and it has to keep working.
**Before any command with `-v` in it on the host, take a dump and check that it
is not empty:**

```sh
docker compose -f /srv/ampeer/docker-compose.yml --env-file /srv/ampeer/.env \
  exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > ~/ampeer-$(date +%F).sql
ls -l ~/ampeer-*.sql
```

Nothing schedules that, nothing checks it, and no workflow in this repository
takes a backup. It is a line to type, which is worth exactly as much as a line
to type; saying so is better than implying a safety net that is not there.

Tear down the local stack with:

```sh
docker compose -f infra/docker-compose.yml -f infra/compose.test.yml \
  --env-file infra/fixtures/env.smoke down -v
```

### Reading the merged file without printing three secrets

`docker compose config` substitutes every variable, and three of the values in
this stack are credentials. Measured on 2026-08-21 against the production file:
the output carried `--token <the connector token>` on the tunnel's command line,
plus `DJANGO_SECRET_KEY` once and `POSTGRES_PASSWORD` twice, in cleartext, into
the terminal and whatever scrollback or CI log it writes to. Use:

```sh
docker compose -f infra/docker-compose.yml -f infra/compose.test.yml \
  --env-file infra/fixtures/env.smoke config --no-interpolate
```

which prints `${CLOUDFLARE_TUNNEL_TOKEN}` instead of its value and answers every
question about the shape of the document. `config --services` is smaller still,
and it does not list `tunnel`, because a service behind a disabled profile is not
in that list.

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
