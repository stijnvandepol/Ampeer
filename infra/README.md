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
`AMPEER_VERSION`. A rollback is that one string plus `docker compose up -d`,
which is also what the deploy job does for you when a release refuses to come
up. Section 5 says what that leaves the stack in.

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
statement about the backup. The first two are still not here, and claiming the
weaker thing accurately is worth more than implying the stronger one. The third
one now exists and section 8 makes it: a dump taken before an advice expired
still holds it, for at most as long as that dump is kept.

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
  the preflight's digest, checks the compose file's digest, checks the backup
  script's digest, runs the preflight, logs in to GHCR, `pull`, confirms the
  pulled digests, records the running release, confirms a recent backup exists,
  `migrate`, `up -d`, falls back if that failed,
  `purge_expired_advice --check`, `docker logout`

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

How long it costs to go red depends on how the image is broken, and the two
cases are far enough apart to be worth telling apart. Both measured on
2026-08-21 against the local stack, from the moment `up -d` was invoked:

| The release | `up -d` fails after | The api container |
|---|---|---|
| starts and exits immediately | **4.7 s** | `Restarting (1)` |
| stays up and never becomes healthy | **84.3 s** | `Up (unhealthy)` |

The second number is the healthcheck's twenty second start period plus its
retries, and it is the one this paragraph used to quote for both. It does not
apply to the first: a container that has exited is not unhealthy, it is gone,
and compose stops waiting for it rather than running the probe three more
times. The table above this one describes a container in `Restarting (1)`, so
it was the fast case being described with the slow case's arithmetic.

Operationally the slow one is the one to know about. A release that crashes is
caught in seconds; a release that runs and does not work holds the deploy for a
minute and a half before anything says so. It also costs availability on a good
release. Measured over a probe every 0.23 seconds across a
release that changes both image tags: the window in which nothing served went
from **0.74 s** to **3.29 s**, because `web` now starts after the api's first
successful probe instead of immediately.

**It is still not a second instance.** By the time `up -d` reports the failure
the previous api container has already been destroyed, because compose recreates
rather than starts a second one, so the site is down at the moment the deploy
finds out.

What changed on 2026-08-21 is what happens next. The job reads the image tag off
the running api container before it replaces it, and a failed `up -d` starts that
tag again. Ending the outage is no longer a person noticing it, editing
`AMPEER_VERSION` in `/srv/ampeer/.env` and running `up -d` by hand.

Three things about that fallback are worth knowing before you need it:

- **The run stays red even when the fallback works.** A fallback that turned the
  run green would mean an outage reported as a successful deploy, and the next
  release cut on top of a version nobody knows is not running.
- **It does not undo the migration.** That ran before the switch and has been
  applied, so the previous release comes back up against the newer schema. That
  is the window the ordering below is built around, and it is safe exactly as
  far as the migration was additive.
- **`/srv/ampeer/.env` is not rewritten**, so a reboot brings back the release
  that is serving. Nothing on the host needs editing to stay where you are.

On a first deploy there is no running container to read a tag from, so there is
nothing to fall back to. The job says so and stops.

**Rehearsed rather than reasoned about**, on 2026-08-21 against the local stack,
because this is machinery that only ever runs during an outage and had never
been executed. A release was built that keeps the real image's healthcheck and
exits on start, and then deployed:

- `up -d` exited **1**, which is what the fallback's condition reads. A failure
  that exited zero would leave the step conditioned on nothing.
- The tag of the running release was read off the container before it was
  replaced, which is the whole of the fallback: `ghcr.io/...ampeer-api:smoke`
  gives `smoke`.
- The failed deploy left **no web container at all**, so the site was down
  rather than degraded. That is worth expecting: there is nothing to serve a
  page from while the api will not start.
- The fallback command brought the site back **5.3 s** after it was invoked, and
  all three services returned.
- `.env` was untouched, so a reboot would have brought back the same release.

So the automatic fallback turns "down until somebody notices" into roughly ten
seconds of outage, if the job runs the failed start and the fallback back to
back. Measured on a developer machine where both images were already present;
on the host the previous image is also already there, so nothing is pulled in
that path either, but the host is not this machine.

### Every deploy is a short outage, and `migrate` runs before it

**There is no second instance.** compose stops `web` and starts it again, so
between those two moments the site serves nothing at all. Measured on
2026-08-21 with the deploy's own command, `up -d --remove-orphans` on a release
that changes both tags, that gap was 3.29 seconds and four consecutive
connection refusals. With `up -d --force-recreate`, which the deploy does
**not** use, the database is recreated too and the gap was 11.62 seconds over
eight refusals.

That one is not fixable from `infra/`. It needs a second instance behind
something that can move traffic, which this deployment does not have.

**`migrate` used to run after the new API was already answering**, and no longer
does. Measured the same day: `/api/advice/health/` returned `200` the moment
`up -d` returned, and the `migrate` step took a further 3.27 seconds. A release
that added a column and read it therefore served errors for the length of a
`docker compose run`, and a migration that failed left it serving them with no
step left to abort.

The deploy now migrates while the previous release is still serving, which
inverts the window rather than closing it:

| | old order | now |
|---|---|---|
| during the window | new code, old schema | old code, new schema |
| a failed migration | new release already serving errors | deploy stops, previous release untouched |
| what makes it safe | nothing can | the migration only adding |

So the ordering buys the safe half of a trade, and the price is a rule that
lives with whoever writes the migration rather than with this file:

> A migration must leave the previous release able to serve. Add a column,
> backfill it, and only drop the old one in a later release.

That rule is not enforceable from a workflow, and nothing here pretends to
enforce it. What the ordering does guarantee is that a migration which fails
stops the deploy while the previous release is still whole.

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

### A database for the test suite, without building the stack

About a tenth of the suite talks to Postgres. Without one those tests do not
fail, they **error**, and pytest reports them separately from failures at the
bottom of a long run. A local run that looks fine at a glance can be missing
them entirely: measured on 2026-08-21, the same suite reported `749 passed` with
89 errors against no database and `838 passed` against one.

That matters more than usual while GitHub Actions minutes are exhausted, because
a local run is then the only run there is.

None of the images have to be built for this. The suite needs a server, not the
stack:

```sh
IMAGE=$(grep -A1 '^  db:' infra/docker-compose.yml | grep image: | sed 's/.*image: //')
docker run -d --name ampeer-devtest -p 5433:5432 \
  -e POSTGRES_USER=ampeer -e POSTGRES_PASSWORD=devtest -e POSTGRES_DB=ampeer "$IMAGE"
```

The image is read out of `docker-compose.yml` rather than written here, so this
is the same server version the host runs and stays that way when the pin moves.
If the grep ever stops matching, `IMAGE` is empty and docker says so on the next
line rather than quietly starting something else.

Port **5433**, not 5432. A development machine often already has a Postgres on
the default port belonging to another project, and that one answers a connection
probe and then refuses the login, which turns the whole suite red for a reason
that has nothing to do with the code.

Then:

```sh
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer \
POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest \
  uv run pytest -q
```

`scripts/gates.sh` reads the same five variables and runs the same command as
part of a full local run. It refuses to guess a password, so without them it
reports `pytest` as NOT RUN rather than passing over a tenth of the suite.

The container holds nothing worth keeping. `docker rm -f ampeer-devtest` when
you are done, and start it again next time; the suite creates and drops its own
test database on every run.

### `down -v` deletes a database, and the project name decides which one

`-v` removes named volumes, and the only named volume in this stack is the one
holding every stored advice. Until 2026-08-21 the commands above ran under the
project name `ampeer`, which is the name the host uses, because
`docker-compose.yml` sets it and compose takes the project name from the last
file that names one. Typed in a checkout on a machine whose docker context points
at the LXC, the teardown below would have destroyed the production database.
At the time nothing in this repository backed that database up. Section 8 is
what changed that, and it is a daily dump rather than an undo.

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

`ampeer-backup.timer` schedules that same dump daily and the deploy job refuses
to migrate without a recent one, so this is no longer the only copy anybody
takes. Type it anyway before a `-v`: the newest scheduled dump can be a day old,
and the rows you are about to destroy may have arrived since.

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

---

## 8. The backup, and what it costs

`ampeer-backup.timer` runs `scripts/backup_db.sh` daily at 04:30 and leaves a
`pg_dump` in `/srv/ampeer/backups`. The script is copied to the host by hand
like the preflight, and the deploy job compares its sha256 against
`BACKUP_SHA256` in the workflow, so a stale copy stops a release instead of
quietly keeping a different number of dumps.

### Why the audit log is the reason

Three tables. `StoredAdvice` can be recomputed, because the inputs are stored
next to the answer. `ProductionCache` can be refetched from PVGIS. `AuditEvent`
cannot be either. It is append-only, it has no retention, and it is the record
that an advice was generated and that a consent was given or withdrawn.

Append-only defends that log against a later developer running
`update_or_create` over it. It does nothing about the disk going away, and the
disk going away is the failure an audit log exists to survive. That is the whole
argument for this section existing.

### What it costs, stated rather than implied

Ninety days after an advice is made the purge deletes it and the service stops
being able to find it. A dump taken the day before still holds it. Three things
bound what that means, and each is a property of the script or the timer rather
than a promise:

- **The timer runs an hour after the purge, not before it.** A dump therefore
  never contains an advice that was already past its date when the dump was
  taken. It does not make the copy disappear; it means the copy is what the
  service could still serve at that moment, rather than a deliberate snapshot of
  rows about to be deleted.
- **Dumps older than seven days are deleted on every run.** One week of restore
  points: short enough that a copy of a purged advice does not outlive it by
  much, long enough that a failure nobody looked at over a weekend is still
  recoverable on the Monday.
- **Restoring one does not extend anything permanently.** The purge runs daily
  and deletes whatever came back past its date within one cycle.

So the question a backup actually raises here is not how long a household's
figures live in the service. It is who can read these files. They are written
`0600` into a directory the script creates `0700`, and `--check` refuses to call
a backup healthy when either is looser than that.

**This is a privacy trade and it is reversible.** Before this section there was
no copy of a purged advice anywhere. There is one now, for at most a week. The
alternative that avoids the trade is dumping only `AuditEvent`, and it was not
taken: a backup that cannot bring the service back is the kind of false comfort
this file exists to avoid.

### What `--check` checks, and where

`backup_db.sh --check` reads the directory and nothing else. No database, no
container, because the question is whether anything is backing this host up, and
a check that needed the service it checks could not answer it on a host where
that service is what broke. In order:

1. the directory exists,
2. it holds at least one `*.sql`,
3. the newest one ends the way a finished `pg_dump` ends,
4. it is no more than 26 hours old,
5. the directory is `700` and the file is `600`.

Permissions are last on purpose. A directory somebody left at `755` must not be
the answer that comes back when there is no dump in it at all.

It runs in two places. `ExecStartPost` on the unit, which asks the question the
exit status did not: the dump reported a byte count, and is the directory now
something a restore could use? And in the deploy job **before `migrate`**,
because this deploy applies migrations, nothing rolls a schema back, and the
moment a recent dump matters is the moment before the first statement runs.

Neither catches a timer that was never enabled, in the sense that
`ExecStartPost` only runs when the unit runs. The deploy step does: it reads the
directory on a host where the timer has never fired and goes red.

### The bootstrap, and the first deploy

A first deploy fails at that step, because there is no backup directory until
the timer has run once. That is deliberate and it is the same shape as the
preflight refusing to start without an env file. Before the first release:

```sh
cp scripts/backup_db.sh /srv/ampeer/backup_db.sh
chmod 700 /srv/ampeer/backup_db.sh
cp infra/systemd/ampeer-backup.* /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ampeer-backup.timer
systemctl start ampeer-backup.service     # once, so a dump exists
systemctl list-timers ampeer-backup.timer
```

### Restoring, measured rather than assumed

A dump nobody has restored is a hypothesis. Measured on 2026-08-21 against
PostgreSQL 16.15 in this stack: a table with two rows was dumped, the database
was dropped with `WITH (FORCE)` and recreated empty, the dump was fed back
through `psql`, and both rows returned with their contents intact.

Two sizes from the same measurement, so a file that looks wrong can be
recognised: an empty database dumps to 643 bytes, and one with a single two-row
table to 2074. A dump is plain SQL and compresses well; nothing here compresses
it, because a corrupted archive is harder to salvage by hand than a truncated
text file.

**What is not covered.** The api container is stopped for none of this, so a dump
is taken while writes are in flight. `pg_dump` takes a consistent snapshot, so
the file is coherent, but it is not a point-in-time recovery: anything written
after the dump is gone. There is no WAL archiving and no off-host copy, so a
failure that takes the LXC with it takes these files as well. Both are their own
round.

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
because `ci.yml` triggers on push to `feat/**`, where no ruleset applies.
`security.yml` is narrower and its earliest trigger is a pull request; the
refusal covers both anyway, because a rule about the whole repository is easier
to keep true than one that has to be rechecked per workflow. The deploy job is the single named exception, and it is only
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
