# The edge image: nginx, the configuration next to this file, and the site as
# `frontend-test` verified it.
#
# It copies `frontend/out` rather than running `next build` itself, on purpose.
# A build here would be a second build, resolving its own dependencies at its
# own moment, and the thing that shipped would no longer be the thing the
# frontend job tested. The build context therefore has to contain a built
# `frontend/out`, and every check below exists because "the context was stale"
# has no other symptom than a site that is quietly wrong.
#
# Pinned by digest. Resolved from the registry on 2026-08-21 with
#   docker buildx imagetools inspect nginx:1.29-alpine
# which returned the digest below. Re-resolve when bumping and write down what
# you got; a tag is a name somebody else can repoint.
FROM nginx:1.31-alpine@sha256:72ba65eb42c10344912a84ff42408db7d34f2feb642204570ab8fc5ffd29f1d3

# Replaces the image's own file rather than adding to conf.d. Three of the
# decisions in it live in the http context, and a partial file would leave the
# defaults in place for exactly those three.
COPY infra/nginx/nginx.conf /etc/nginx/nginx.conf

COPY frontend/out /usr/share/nginx/html

# Four assertions about the artifact, all of which fail loudly here rather than
# quietly in production.
RUN set -eu; \
    # The site exists at all. A `COPY` of an empty directory succeeds.
    test -f /usr/share/nginx/html/index.html; \
    # The fallback target exists. try_files pointing at a file that is not there
    # produces the same 404 the fallback was written to prevent, and it would
    # produce it only for visitors, never in a test of the configuration text.
    test -f /usr/share/nginx/html/advies/index.html; \
    # The bundle does not call the API on the visitor's own machine.
    # `NEXT_PUBLIC_API_BASE` is inlined at build time and api.ts falls back to
    # http://127.0.0.1:8000 when it is unset, so a site built without that
    # variable set to the empty string ships a client that asks localhost for
    # every advice: a hundred percent broken, on a page that renders perfectly.
    # Build the export with NEXT_PUBLIC_API_BASE= so the client uses relative
    # paths, which is what makes the same origin decision real.
    if grep -raqF '127.0.0.1:8000' /usr/share/nginx/html; then \
        echo 'frontend/out was built without NEXT_PUBLIC_API_BASE= ; the bundle points at localhost' >&2; \
        exit 1; \
    fi; \
    # And the configuration parses, so a typo is a red build and not a
    # container that restarts on the host.
    #
    # Tested through a copy with the upstream name replaced, because `nginx -t`
    # resolves every upstream while it parses and there is no `api` service
    # during a build. That resolution is not an artefact of the test: nginx does
    # it at startup too, so this container refuses to start while the name `api`
    # does not resolve, which is why the compose file has web depend on api and
    # why a stack whose API never comes up has no static site either. The copy
    # changes one hostname and nothing else, so every other line is checked
    # exactly as it ships, and the served file is the original.
    #
    # Measured on 2026-08-21 rather than reasoned about, because the consequence
    # is larger than the sentence above suggests. Stop `api` and restart this
    # container and it crash-loops on
    #   nginx: [emerg] host not found in upstream "api" in /etc/nginx/nginx.conf
    # serving nothing at all, not a page with a broken API. The same happens on
    # its own whenever the api image is broken: Docker drops a restarting
    # container's name from the network's DNS, so an api that cannot start takes
    # the statically exported site down with it, and that site needs neither an
    # API nor a database. `restart: unless-stopped` recovers it if the api
    # eventually starts; if the database never initialises, it does not.
    #
    # Nothing in this file or in docker-compose.yml can decouple them. What can:
    # a `resolver` plus a variable `proxy_pass` in infra/nginx/nginx.conf, which
    # defers the lookup to request time so nginx starts without the api and
    # answers 502 for /api/ while serving every page. If that lands, this `sed`
    # keeps working as long as the literal `http://api:8000` still appears
    # somewhere in the file, and stops being needed at all once the upstream is
    # a variable, because nginx then does not resolve it while parsing.
    sed 's|http://api:8000|http://127.0.0.1:8000|' /etc/nginx/nginx.conf > /tmp/syntax-check.conf; \
    nginx -t -c /tmp/syntax-check.conf; \
    rm /tmp/syntax-check.conf

# The master process stays root because it binds port 80 and because the
# tunnel's ingress on the Cloudflare side names that port, which is
# configuration nobody here can change. Workers drop to the unprivileged
# `nginx` user, which is what serves every request. Moving to the unprivileged
# variant means moving to 8080 and changing the tunnel route, which is Stijn's
# to do, and is noted here rather than left to be discovered.
EXPOSE 80

# The compose file gives `web` no healthcheck, and a container that is up while
# serving nothing is the failure this project keeps meeting. This one asks for
# the home page over the real listener, so a configuration that parses but
# serves an empty root is visible as unhealthy.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
