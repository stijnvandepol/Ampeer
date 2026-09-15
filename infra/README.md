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

## 0. What a fresh host needs, in one list

Two things, and neither can come from a git tag. That is not a coincidence: it
is the whole reason they are the two that are left.

| What | Where | Why it is not in the repository |
|---|---|---|
| `/srv/ampeer/.env` | written on the host, from `infra/.env.example` | it holds a Django signing key, a database password and a mail API key |
| the NEDU consumption profile | at whatever path `AMPEER_NEDU_PROFILE_PATH` names, for example `/srv/profiles/nedu-profiles-2025.csv` | `data/` is gitignored; the profile is not ours to redistribute |

Everything else arrives with the deploy, which checks the tag out. Until
2026-09-14 three more files had to be copied here by hand and were verified by
sha256, and four releases in a row stopped on the first of them. That list is
gone along with the copying.

**The profile must be a readable FILE before the stack comes up.** If the path
does not exist, the Docker daemon creates an empty directory there and mounts
it over the place the CSV should be: the container starts, the process is
alive, and every advice fails. Section 2 is the whole story.

It does not have to come from a developer machine. The host can produce it from
the published source, which is the same thing `tools/ingest_profiles.py` does:

```sh
# on the host, in a container, so nothing has to be installed there
docker run --rm \
  -v /srv/profiles:/out \
  -v /root/actions-runner/_work/Ampeer/Ampeer/tools:/tools:ro \
  python:3.12-slim \
  sh -c "pip install -q requests && python /tools/ingest_profiles.py 2025 --target /out"
```

**Verify, from the host itself:**

```sh
bash scripts/preflight_env.sh /srv/ampeer/.env
```

It names every missing variable at once, checks the profile path is a readable
file, and never prints a value. Exit zero means there is nothing left to do
here.

Two more things are the host's own and are described in section 3: the
retention timer and the outbox timer, neither of which this repository
installs.

## What runs

Three services, in `docker-compose.yml`:

| Service | Image | What it does |
|---|---|---|
| `db` | `postgres:16-alpine`, by digest | The database, on a named volume that survives `down` |
| `api` | `ghcr.io/stijnvandepol/ampeer-api:<tag>` | Django on gunicorn, uid 10001, no port of its own |
| `web` | `ghcr.io/stijnvandepol/ampeer-web:<tag>` | nginx: the exported site, and `/api/` to `api` |

**One port listens, and it is nginx.** `web` publishes **8080** on the host,
which forwards to nginx on 80 inside the container, and nothing else publishes
anything. A tunnel operated outside this stack points at `<host>:8080`; this
repository does not run, configure or hold a credential for that tunnel.

8080 rather than 80 since 2026-09-14. It leaves port 80 on the host free, it
asks for no privileged port, and it is the port the local override already
used, so the address you rehearse against and the address on the host are now
the same string.

**Check it is free before the first deploy.** 8080 is the port half the world
reaches for, so unlike 80 it may already be taken by something a person started
and forgot. Docker does not share it: the container simply fails to start and
the deploy is red on `Start it`, which is the right failure and an annoying one
to meet for the first time at a release.

```sh
ss -lntp 'sport = :8080'
```

Nothing listed means nothing to do.

Docker publishes through its own iptables chain, which is evaluated before a
host firewall's INPUT rules, so **restricting who may reach port 8080 is a
decision for the host** and cannot be made in the compose file. On a machine
whose only other occupant is the connector, binding it to the interface that
connector uses is the smallest opening that works.

**One hostname, and what happens if a second one appears.** `server_name _` in
`infra/nginx/nginx.conf` is a catch all: nginx answers to any `Host` it is sent.
What decides which names are real is `DJANGO_ALLOWED_HOSTS`, and it names
`ampeer.nl`.

So a `www.ampeer.nl` routed to this stack would be the worst kind of half
working. The exported pages are static files and would render perfectly, and
every one of them would then call `/api/...` on the host the visitor typed.
Django refuses a `Host` outside `ALLOWED_HOSTS` before any view runs, so the
page appears and the button fails, which is harder to diagnose than a site that
is simply down. Every canonical tag says `https://ampeer.nl/` as well, so the
apex is the only name a search engine should ever hold.

Measured on 2026-09-14: `ampeer.nl` resolves to Cloudflare and answers 502 from
their edge, which is a tunnel whose origin is not up; `www.ampeer.nl` does not
resolve at all. That second one is the safe state and not the finished one:
somebody who types the `www` gets a DNS error. If it is added, make it a
redirect to the apex in DNS or at the edge, and not a second route into this
stack.

**Why the firewall rule is not optional.** nginx appends to `X-Forwarded-For` and
`DJANGO_NUM_PROXIES` counts hops from the right of it, which is correct for
every request that arrives through the connector and is the reason a visitor
cannot buy themselves a fresh rate limit by sending a header. A caller who
reaches port 8080 *without* going through the connector is one hop short: the
value the throttle lands on is then whatever they wrote, and they can rotate it
per request. Forty requests with a rotating header produced zero 429s when this
was measured on 2026-08-21, which is what set `NUM_PROXIES` in the first place.

Until the stack published a port this was unreachable by construction and the
firewall was defence in depth. It is now the control. Allow port 8080 from the
connector's address and from nothing else.

`tests/test_infra.py` asserts on every pull request that `api` and `db`
publish nothing. That is the property worth protecting: nginx is what strips
`X-Forwarded-Proto`, Django's only TLS signal, and `X-Forwarded-For`, which
the throttle counts, and a caller who reached `api:8000` directly could forge
both.

The two images built from this repository are pulled at the release tag in
`AMPEER_VERSION`. A rollback is that one string plus `docker compose up -d`,
which is also what the deploy job does for you when a release refuses to come
up. Section 5 says what that leaves the stack in.

---

## 1. The environment file

Copy `infra/.env.example` to **`/srv/ampeer/.env`** on the host and fill it in.
It is outside git on purpose and there is no default for anything in it: a
default for a secret is a secret in the repository with extra steps.

`prod.py` refuses to start without these thirteen, and gives none of them a value:

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
| `AMPEER_MAIL_TRANSPORT` | `resend` on a host. The preflight refuses every other value here: `file` writes each mail to a file inside the container and delivers none |
| `RESEND_API_KEY` | The Resend key with send permission for the domain below. A credential |
| `AMPEER_MAIL_FROM` | The sender a household sees, `noreply@ampeer.nl`, on a domain verified at Resend with the SPF and DKIM records it hands out |
| `AMPEER_SITE_ORIGIN` | Where the links in a mail point, `https://ampeer.nl`. The page reads the token off the fragment of that origin's `/account/` route |

Two more names are read by `docker-compose.yml` and are not in that list because
`prod.py` never sees them:

| Name | What goes in it |
|---|---|
| `AMPEER_VERSION` | The release tag both images are pulled at. The deploy job exports it from the tag it is deploying, and a shell variable beats the file, so this only matters when starting the stack by hand |

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
all. Two is right for the host because there are two hops, the connector and
nginx, and that stays true now that the connector runs outside this stack: it
is still in front of nginx. The local test override uses one, because there is
no connector in front of a developer machine.

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

### The outbox timer is installed the same way

`infra/systemd/ampeer-mail.service` and `infra/systemd/ampeer-mail.timer`
send the password reset and address confirmation mails, every minute.
**Nothing in this repository installs, enables or starts them either.**

```sh
cp infra/systemd/ampeer-mail.* /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ampeer-mail.timer
```

**Verify:**

```sh
systemctl list-timers ampeer-mail.timer       # NEXT must be within a minute
docker compose --env-file /srv/ampeer/.env -f /srv/ampeer/docker-compose.yml run --rm --entrypoint python api backend/manage.py send_outbound_mail --check
```

The second command exits non-zero on two different failures, and it names the
counts apart: an unsent mail older than fifteen minutes, and a mail the sender
gave up on within the last day. The first is a timer that has stopped. The
second is a status nothing will retry, a wrong `RESEND_API_KEY` being the
likeliest, which fails every mail on its first attempt and therefore leaves
nothing waiting for the first count to find. The deploy job runs the command
after `migrate` for the same reason it runs the purge check there. It does not
notice a timer that was never enabled until the first mail is fifteen minutes
late, which for a household is already too late; only `list-timers` answers
that question, and it is written down here rather than papered over.

Every run of `send_outbound_mail` sends at most fifty rows (`--max`, tunable), so a large
backlog drains over several ticks of the timer rather than holding one transaction open for
the whole queue at once.

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
  the tag out, places the host's copies, runs the preflight, logs in to GHCR, `pull`, confirms the pulled
  digests, records the running release, confirms a recent backup exists,
  `migrate`, `up -d`, falls back if that failed,
  `purge_expired_advice --check`, `send_outbound_mail --check`, `docker logout`

It checks the tag out since 2026-09-14, and until then it did not. Three files
had to be copied to `/srv/ampeer` by hand and were verified here by sha256, and
four releases in a row stopped on the first of them: v0.2.0, v0.3.0, v0.4.0 and
v0.5.0 all died on `no preflight at /srv/ampeer/preflight_env.sh`. Nothing was
ever deployed at all.

What the absence bought does not survive being looked at. Whoever pushes a tag
already decides every step this job runs, because the workflow file comes from
that tag; the gate is that it triggers on `v*` and nothing else, and that has
not moved. So the checkout costs a smaller blast radius after a compromise that
would already own the job, and it buys a deploy that works without anybody
remembering anything.

Still no `docker build`: the host pulls what CI built and assembles nothing.

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

**Rehearsed on 2026-08-21**, because that last sentence had never been executed
either. A migration was mounted into the api image that adds a column and then
asks for an index on a column that does not exist, and it was run the way the
deploy runs it, with the site being probed four times a second throughout:

- `migrate` exited **1**, so the job stops there and never reaches `up -d`.
- The site served **every one of the eleven probes** taken while it ran. The
  previous release was untouched, because nothing had been switched.
- The database was untouched as well. The column the migration had already
  added was gone afterwards and the migration was not recorded as applied.
  PostgreSQL runs DDL inside a transaction and Django wraps each migration in
  one, so a migration that fails leaves nothing of itself behind.

**That last point holds per migration and not per release**, which is the part
worth knowing before it matters. The same rehearsal with two migrations, the
first adding a column and the second failing, left the first applied: its column
was present and its name was in `django_migrations`. Only the failing one rolled
back.

So an aborted deploy can leave the previous release running against a schema
that is part of the way to the next one. It keeps serving, and it keeps serving
for exactly as long as those migrations only added, which is the rule above.
That is a second reason for it, and a better one than the window between
`migrate` and `up -d`: the window lasts seconds, and this state lasts until
somebody deploys again.

### The digest check, and the window it closes

`docker-compose.yml` pulls `:${AMPEER_VERSION}`, and between the build job and
the pull sits the `production` review, which can take hours. A tag is a name:
anyone holding `packages: write` on the repository can repoint
`ampeer-api:v0.1.0` while that review is open, and the reviewer then approves
the run they read while the host pulls whatever the tag says at pull time.
Nothing in the run would look wrong.

So the pull is checked rather than pinned. `pull` has already resolved the tag,
and the step reads the digest the daemon recorded for what it fetched and
compares it with the digest the build job says it pushed.

**Rehearsed on 2026-08-21**, because a control that has never been run is a
control nobody has seen work. The step was lifted out of the workflow unchanged
and driven with two locally built images standing in for a good release and a
repointed one:

| The tag points at | The step |
|---|---|
| what the build published | exits 0 |
| a different image | exits 1, printing both digests and naming what happened |
| nothing, because the build published no digest | exits 1, saying so |
| an image the host does not have | exits 1, on the daemon's own error |

All three failures are closed rather than open, which is the property that
matters for a control whose whole job is to refuse.

One thing that surprises a person rehearsing this locally: an image built here
and never pushed still reports a `RepoDigests` entry, so the check runs against
it happily. On the host nothing is built, so the digest there is always the one
the registry handed over with the pull, and this only matters when reading the
output of a local rehearsal and wondering why it looks like a real pull.

**What this does not cover**, stated rather than implied: a rollback. That is an
operator running `docker compose up -d` with an older `AMPEER_VERSION`, with no
build job in that path to say what the digest should be and no CI run at all, so
a tag repointed weeks ago is pulled without anything objecting. It is the price
of the tag being usable while CI is not, and it is the operation the tag exists
to make easy, so it is the one to be careful with.

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

`infra/compose.test.yml` is an override that narrows the published port to
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

### The same gates, on the operating system that decides them

```sh
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest   bash scripts/gates_linux.sh
```

Development happens on Windows and the pipeline runs on Linux, and a green run
here is not a green run there. Three tests skip on this filesystem with "this
filesystem does not carry POSIX modes": they are the ones asserting a dump is
`0600` inside a `0700` directory, which is a claim `docs/dpia.md` makes about
who can read a backup. Until 2026-08-22 they had never run anywhere.

The script defines no gates of its own. It builds a container from the Python
and uv versions this project already pins, puts the git index into it and runs
`scripts/gates.sh` there, so there is one place that says what a gate is. It
runs the Python half; the frontend half needs Node and its behaviour does not
differ between the two systems, so that is left to CI.

The index and not the working tree, because the checks that ask git what it
tracks read the index. Running the gates before `git add` says nothing about
what a commit will contain, which is how a red test reached the branch tip on
2026-08-22. Without Docker the script reports NOT RUN and exits zero, the same
answer `scripts/gates.sh` gives for a gate it cannot reach.

With a database, a browser and gitleaks present, a full local run leaves nothing
NOT RUN. That matters more than it sounds while GitHub Actions is unavailable,
because the local run is then the only run there is. The browser comes from
`pnpm exec playwright install --with-deps chromium` in `frontend/`, and gitleaks
needs no separate install: `pre-commit install-hooks` fetches the version
`.pre-commit-config.yaml` pins, which is the one the `secrets` job downloads,
and the runner finds it in that cache.

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

### Reading the merged file without printing two secrets

`docker compose config` substitutes every variable, and two of the values in
this stack are credentials. Measured on 2026-08-21 against the production file:
when a connector token was a third of them: the output carried
`DJANGO_SECRET_KEY` once and `POSTGRES_PASSWORD` twice, in cleartext, into
the terminal and whatever scrollback or CI log it writes to. Use:

```sh
docker compose -f infra/docker-compose.yml -f infra/compose.test.yml \
  --env-file infra/fixtures/env.smoke config --no-interpolate
```

which prints `${DJANGO_SECRET_KEY}` instead of its value and answers every
question about the shape of the document. `config --services` is smaller still.

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
things to prove against a running stack. They were first run on 2026-08-21
against the override above and their output is in the commit that added this
file, and last run on 2026-09-13 against v0.3.0, where all seven passed along
with the twenty-eight assertions in `tests/test_stack_smoke.py`.

All seven pass as written. The first used to be the exception: it asked for all
four services up and healthy, and the override that makes a local run possible
stopped the fourth, a connector, from starting, because one started from a
developer machine would register a route to a tunnel serving a real domain.
That service is gone from this stack, so the check is now three of three.

This paragraph said both "six of the seven pass" and "all seven pass" in
adjacent sentences between 2026-09-13 and the same day, which is what a
half-finished edit looks like when the thing it was editing is prose.
