"""nginx configuration read as text, because two lines in it decide whether the
product works and whether it keeps a promise the rest of the project enforces.

Nothing here starts nginx. These are properties of the file; Task 6 drives the
running server, and the running server is where the log was actually read
before this file was believed.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

CONF = Path(__file__).resolve().parent.parent / "infra" / "nginx" / "nginx.conf"
TEXT = CONF.read_text(encoding="utf-8")

#: The same file with comment lines removed. Every test that looks for a
#: directive must read this and not TEXT: the comments here explain the
#: directives at length, quoting them, and a grep over the prose matches the
#: thing it was written to describe. That has now happened twice in this
#: repository, once in a systemd unit and once here.
DIRECTIVES = chr(10).join(line for line in TEXT.splitlines() if not line.lstrip().startswith("#"))

#: nginx variables that carry either the request path or the caller's address.
#: A log format naming one of these writes the token, the visitor's IP, or the
#: pair of them to a file whose retention nobody in this project has chosen.
#: Matched as whole variable names, because `$request_method` and
#: `$request_time` are fine and a substring test would forbid both.
LEAKY_LOG_VARIABLES = frozenset(
    {
        "request",  # the request line, token and all
        "request_uri",  # the raw path, token and all
        "uri",  # the normalised path, token and all
        "document_uri",  # an alias of $uri
        "http_referer",  # /advies/<token>/ is the referer of every asset it loads
        "remote_addr",
        "binary_remote_addr",
        "realip_remote_addr",
        "http_x_forwarded_for",
        "proxy_add_x_forwarded_for",
    }
)


def variables(text: str) -> set[str]:
    """Every nginx variable named in a fragment, as bare names."""
    return set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", text))


def log_formats() -> dict[str, str]:
    """Every `log_format` this file defines, by name."""
    return {
        name: body for name, body in re.findall(r"log_format\s+(\w+)\s+(.*?);", TEXT, re.DOTALL)
    }


def access_logs() -> list[str]:
    """The argument list of every `access_log` directive, in file order."""
    return [args.strip() for args in re.findall(r"access_log\s+([^;]+);", TEXT)]


def test_the_advice_route_falls_back_to_the_built_page() -> None:
    """The site is statically exported, so there is one built advice page and
    no route per token.

    Without this, the visitor who has just answered four questions gets a 404,
    not only the recipient of a shared link: the flow ends in a full navigation
    to /advies/<token>/. Their advice is computed, stored, and charged against
    their hourly budget, and they never see it.
    """
    block = re.search(r"location\s+/advies/\s*\{([^}]*)\}", TEXT, re.DOTALL)
    assert block, "no location block for /advies/"
    assert "try_files" in block.group(1)
    assert "/advies/index.html" in block.group(1)


def test_the_token_never_reaches_the_access_log() -> None:
    """The audit log stores the token hashed and no IP at all. nginx writing
    `client_ip "GET /api/advice/<token>/"` puts exactly the pairing this
    project refuses to make on disk, with a retention nobody here chose."""
    block = re.search(r"location\s+/api/advice/\s*\{([^}]*)\}", TEXT, re.DOTALL)
    assert block, "no location block for /api/advice/"
    body = block.group(1)
    assert "access_log off" in body or re.search(r"access_log\s+\S+\s+\w+", body), body


def test_every_access_log_names_a_format_this_file_defines() -> None:
    """The previous test passes for `access_log /dev/stdout combined;`, and
    `combined` is the built-in format that logs the address and the request
    line: the exact string this project refuses to write down.

    So the gate is not that a format is named, it is that the named format is
    one whose definition is visible here and readable by the next test. A
    format that nginx ships with is a format nobody in this repository chose.
    """
    defined = set(log_formats())
    assert defined, "this file defines no log_format at all"
    for args in access_logs():
        if args.split()[0] == "off":
            continue
        parts = args.split()
        assert len(parts) >= 2, f"access_log without an explicit format: {args!r}"
        assert parts[1] in defined, f"{parts[1]!r} is not defined here: {sorted(defined)}"


def test_no_log_format_can_write_a_token_or_an_address() -> None:
    """Read the formats rather than trusting their names.

    `$request` and `$request_uri` carry the token on two routes, `$http_referer`
    carries it on every asset the advice page loads, and `$remote_addr` with
    `$http_x_forwarded_for` carry the visitor. None of them belongs in a file
    that outlives the row it describes.
    """
    for name, body in log_formats().items():
        leaks = variables(body) & LEAKY_LOG_VARIABLES
        assert not leaks, f"log_format {name} writes {sorted(leaks)}"


def test_the_logged_route_is_stripped_of_the_token_on_both_paths_that_carry_one() -> None:
    """Two routes carry a token, not one.

    `/api/advice/<token>/` is the one the design names. `/advies/<token>/` is
    the page the visitor is sent to after answering, it is served by this same
    nginx, and its path carries the same secret. A rewrite that covers only the
    API leaves the token in the log anyway, on the request that happens first.
    """
    from advice.urls import TOKEN_LENGTH

    block = re.search(r"map\s+\$uri\s+\$(\w+)\s*\{(.*?)\n\s*\}", TEXT, re.DOTALL)
    assert block, "no map rewriting $uri into a loggable route"
    arms = block.group(2)
    assert f"{{{TOKEN_LENGTH}}}" in arms, (
        f"the map does not match a {TOKEN_LENGTH} character token; "
        "advice.urls.TOKEN_LENGTH moved and this did not"
    )
    for route in ("/api/advice/", "/advies/"):
        assert route in arms, f"the map leaves the token in {route}<token>/: {arms}"


def test_the_forwarded_proto_is_set_to_a_value_nginx_chooses() -> None:
    """prod.py trusts X-Forwarded-Proto, which is only correct if the proxy
    overwrites it rather than passing the caller's along.

    The value is a constant and deliberately not `$scheme`. Cloudflare
    terminates TLS and the connector speaks plain HTTP to this container, so
    `$scheme` is `http` here on every request that arrived over `https`.
    Django would then see an insecure request, SECURE_SSL_REDIRECT would answer
    301 to the same URL, and the tunnel would deliver it back: a redirect loop
    on every API call. See the comment above the directive.
    """
    values = [
        v.strip() for v in re.findall(r"proxy_set_header\s+X-Forwarded-Proto\s+([^;]+);", TEXT)
    ]
    assert values, "nginx does not set X-Forwarded-Proto"
    assert all(v == "https" for v in values), values
    assert "$scheme" not in " ".join(values), values


def test_the_forwarded_for_header_is_appended_the_standard_way() -> None:
    """DJANGO_NUM_PROXIES counts hops from the right of X-Forwarded-For.

    Appending is what makes that count safe: a caller who forges the header
    only makes the list longer on the left, and the hop the count lands on is
    still the one the connector wrote. Overwriting instead would make every
    visitor look like the connector and share one rate limit; dropping the
    append would let a caller who controls the count buy a fresh limit, which
    was measured on this API on 2026-08-21.
    """
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in TEXT


def test_no_header_is_forwarded_with_a_value_the_caller_supplied() -> None:
    """`$http_x_forwarded_proto` on the right of a proxy_set_header is the
    whole bug this file exists to prevent, written in one variable."""
    forwarded = re.findall(r"proxy_set_header\s+\S+\s+([^;]+);", TEXT)
    leaks = [v for v in forwarded if "$http_x_forwarded" in v]
    assert not leaks, leaks


def test_the_server_does_not_announce_its_version() -> None:
    assert "server_tokens off;" in TEXT


def test_the_body_limit_is_far_below_what_django_would_accept() -> None:
    """Django's own cap is DATA_UPLOAD_MAX_MEMORY_SIZE, 2.5 MB by default, and
    the largest legitimate request here is a refine POST of about 400 bytes.
    Between those two numbers sit two and a half megabytes that would be read
    into the API's memory before being refused. They should not travel that
    far."""
    limit = re.search(r"client_max_body_size\s+(\d+)([kKmM]?);", TEXT)
    assert limit, "no client_max_body_size"
    size, unit = int(limit.group(1)), limit.group(2).lower()
    assert unit != "m" and size * (1024 if unit == "k" else 1) <= 64 * 1024, limit.group(0)


def test_nothing_is_proxied_except_the_api() -> None:
    """A proxy_pass outside /api/ is a way for the static site to become a
    forwarder to something nobody reviewed."""
    passes = re.findall(r"proxy_pass\s+([^;]+);", DIRECTIVES)
    assert all("api" in target for target in passes), passes
    blocks = re.findall(r"location\s+(\S+)\s*\{([^}]*)\}", TEXT, re.DOTALL)
    proxying = [name for name, body in blocks if "proxy_pass" in body]
    assert all(name.startswith("/api/") for name in proxying), proxying


#: A token in the shape the router actually produces: 22 url-safe characters.
#: The one below is the value that was read out of a live throttle row on
#: 2026-08-21, which is where this whole family of findings started.
SAMPLE_TOKEN = "TESTtokenTESTtoken0000"


def map_arms() -> tuple[list[tuple[str, str]], list[tuple[str, str]], str | None]:
    """The `map $uri` block as nginx reads it.

    nginx compares an exact string source first, whatever order it is written
    in, then the regular expressions in the order they are defined, and only
    then falls through to `default`. Modelling that here rather than reading
    the file top to bottom is the difference between testing the map and
    testing the way it happens to be laid out.
    """
    block = re.search(r"map\s+\$uri\s+\$(\w+)\s*\{(.*?)\n\s*\}", TEXT, re.DOTALL)
    assert block, "no map rewriting $uri into a loggable route"
    exact: list[tuple[str, str]] = []
    regexes: list[tuple[str, str]] = []
    default: str | None = None
    for raw in block.group(2).splitlines():
        line = raw.split("#", 1)[0].strip().removesuffix(";").strip()
        if not line:
            continue
        source, value = shlex.split(line)
        if source == "default":
            default = value
        elif source.startswith("~"):
            regexes.append((source.lstrip("~*"), value))
        else:
            exact.append((source, value))
    return exact, regexes, default


def logged_route(uri: str) -> str:
    """What nginx would put in the access log for this path."""
    exact, regexes, default = map_arms()
    for source, value in exact:
        if source == uri:
            return uri if value == "$uri" else value
    for pattern, value in regexes:
        if re.search(pattern, uri):
            return uri if value == "$uri" else value
    assert default is not None, "the map has no default"
    return uri if default == "$uri" else default


def test_the_map_never_falls_through_to_the_path_itself() -> None:
    """The whole finding in one assertion.

    `default $uri` makes this map an allowlist that fails open: every path it
    does not recognise is written to the access log verbatim, and two of this
    site's prefixes carry a secret in the path. Measured on 2026-08-21 against
    a running stack: `GET /api/advice/<token>` without the trailing slash is a
    301 from Django and was logged with the token in it.
    """
    _, _, default = map_arms()
    assert default is not None, "the map has no default"
    assert default != "$uri", "the map's default writes the path, token and all"


def test_no_path_under_a_token_carrying_prefix_is_logged_verbatim() -> None:
    """Not just the canonical route.

    Django answers the missing trailing slash with a 301 and nginx logs the
    request either way, so the near-miss is the case that matters. So is any
    suffix under it, which nobody has to enumerate to try.
    """
    hostile = [
        f"/api/advice/{SAMPLE_TOKEN}",
        f"/api/advice/{SAMPLE_TOKEN}/",
        f"/api/advice/{SAMPLE_TOKEN}//",
        f"/api/advice/{SAMPLE_TOKEN}/x",
        f"/api/advice/{SAMPLE_TOKEN}.json",
        f"/api/advice/x/{SAMPLE_TOKEN}/",
        f"/advies/{SAMPLE_TOKEN}",
        f"/advies/{SAMPLE_TOKEN}/",
        f"/advies/{SAMPLE_TOKEN}/index.html",
        f"/advies/{SAMPLE_TOKEN}.html",
        f"/advies/x/{SAMPLE_TOKEN}",
    ]
    for uri in hostile:
        assert SAMPLE_TOKEN not in logged_route(uri), uri


def test_the_two_canonical_routes_are_still_labelled_rather_than_lumped_together() -> None:
    """Failing closed must not cost the log its reason to exist."""
    assert logged_route(f"/api/advice/{SAMPLE_TOKEN}/") == "/api/advice/:token/"
    assert logged_route(f"/advies/{SAMPLE_TOKEN}/") == "/advies/:token/"


def test_every_token_free_api_route_is_still_named_in_the_log() -> None:
    """Read from the URLconf, not written down twice.

    A blanket label for everything under /api/advice/ would fail closed and
    also make the log unable to say whether the compute endpoint is being hit
    at all, which is most of what an access log on this service is for. So the
    routes that provably carry no token are listed, and they are listed from
    the router rather than from memory.
    """
    from advice.urls import urlpatterns

    token_free = [
        f"/api/advice/{pattern.pattern}"
        for pattern in urlpatterns
        if "token" not in pattern.pattern.regex.groupindex
    ]
    # Four since 2026-09-02, when the aggregate counter endpoint arrived.
    # The literal is the tripwire: it is what made a new route announce
    # itself here rather than quietly reaching the internet with no arm in
    # the log map, which is how a path stops being distinguishable from
    # every other in an access log.
    assert len(token_free) == 4, token_free
    for route in token_free:
        assert logged_route(route) == route, route


def test_a_path_that_cannot_carry_a_token_is_logged_as_itself() -> None:
    """The other half. A log that says `/other` for every asset and every page
    answers nothing, and this map exists to keep the log useful."""
    for uri in ("/", "/berekenen/", "/_next/static/chunk-abc123.js", "/404.html"):
        assert logged_route(uri) == uri, uri


def test_the_built_advice_page_is_still_told_apart_from_a_refusal() -> None:
    """$uri is what it is when the line is written, not what arrived.

    `try_files ... /advies/index.html` is an internal redirect, so a visitor
    opening /advies/<token>/ is logged against the fallback target. Measured
    against a running nginx on 2026-08-21: all three /advies/ requests logged
    as /advies/index.html, before this change and after it. That is also why
    the token never reached the log on that route in the first place, and why
    an arm for the served page has to exist: without it the successful case and
    the refused one are one label.
    """
    assert logged_route("/advies/index.html") == "/advies/index.html"
    assert logged_route("/advies/nonsense") == "/advies/:other"


def test_the_upstream_is_resolved_per_request_and_not_at_startup() -> None:
    """A literal upstream name makes web refuse to start while api is down.

    Measured 2026-08-21: with `proxy_pass http://api:8000;` and the api
    container stopped, nginx logged `[emerg] host not found in upstream "api"`
    and the whole site returned 000 — not a 502 on /api/ alone. A statically
    exported page that needs no API and no database was dark because Postgres
    would not start, and Docker's restart policy does not honour depends_on, so
    on a host reboot the ordering that protects `docker compose up` is absent
    exactly when nobody is logged in.

    Verified after the change against a running container with no api present
    at all: site 200, /api/ 502, zero emerg lines.
    """
    assert "resolver 127.0.0.11" in DIRECTIVES, "no resolver, so a variable upstream cannot work"

    literals = re.findall(r"proxy_pass\s+http://(?!\$)([^;]+);", DIRECTIVES)
    assert not literals, f"these upstreams are resolved once at startup: {literals}"


def test_every_variable_upstream_carries_the_request_uri() -> None:
    """The half of that change that fails silently.

    `proxy_pass http://api:8000;` with a literal and no URI forwards the request
    path unchanged. With a variable it does not, and every path arrives at the
    API as "/" — so estimate, refine and every token read would hit the same
    route and the site would look broken in a way that points at Django.

    Verified against an echo upstream: /api/advice/estimate/ and
    /api/advice/<token>/ both arrived whole.
    """
    variables = re.findall(r"proxy_pass\s+(http://\$[^;]+);", DIRECTIVES)
    assert variables, "no variable upstream to check"
    for target in variables:
        assert target.endswith("$request_uri"), (
            f"{target} drops the path: every request would arrive as /"
        )


# ---------------------------------------------------------------------------
# The headers that protect the page, which Django never sees
# ---------------------------------------------------------------------------


def _headers() -> dict[str, str]:
    """Every `add_header` in the file, by header name."""
    found = {}
    for name, value in re.findall(r'add_header\s+(\S+)\s+"([^"]*)"', DIRECTIVES):
        found[name] = value
    return found


def _blocks(keyword: str) -> list[str]:
    """The body of every block opened by ``keyword``, brace matched."""
    bodies = []
    for match in re.finditer(rf"^\s*{keyword}\s[^{{]*\{{", DIRECTIVES, re.MULTILINE):
        depth, start = 0, match.end() - 1
        for index in range(start, len(DIRECTIVES)):
            if DIRECTIVES[index] == "{":
                depth += 1
            elif DIRECTIVES[index] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(DIRECTIVES[start + 1 : index])
                    break
    return bodies


def test_the_page_carries_the_headers_that_protect_its_own_url() -> None:
    """Nothing read these until 2026-08-23, on either side of the boundary.

    Django's equivalents are asserted in tests/test_backend_settings.py, and
    Django serves the API. The page a household actually reads is the exported
    Next.js build handed out by this server, so these four are the ones that
    apply to it, and the comment above them says exactly that.

    Referrer-Policy is the one with a name in this project. The advice lives at
    /advies/<token>/ and that URL is a working, unauthenticated link to one
    household's answers: postcode, consumption, roof. Under a permissive policy
    the browser puts that whole URL in the Referer header of every request to
    another host. The rest of this file goes to some length to keep the token
    out of an access log; the same token in an outbound header would be the
    same leak through a door nobody was watching.

    Neither instrument saw it. `manage.py check --deploy` reads Django settings
    and does not know this file exists, and setting Django's own
    SECURE_REFERRER_POLICY to "unsafe-url" was measured to leave both the deploy
    check and the whole test suite green.
    """
    headers = _headers()
    assert headers.get("Referrer-Policy") == "same-origin", (
        f"Referrer-Policy is {headers.get('Referrer-Policy')!r}, and /advies/<token>/ is a "
        "working link to one household's answers"
    )
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"

    policy = headers.get("Content-Security-Policy", "")
    for directive in (
        "default-src 'self'",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
    ):
        assert directive in policy, f"the policy no longer carries {directive!r}: {policy!r}"


def test_the_policy_admits_google_analytics_and_no_other_third_party() -> None:
    """Since 2026-09-15 a visitor who says yes to the measurement question
    loads gtag.js, and the policy has to let exactly that through: the script
    host, the two collection hosts, and the pixel fallback. Everything else a
    tag on a Google page would reach, Tag Manager containers, doubleclick, an
    ads host, stays refused by the browser whatever the code does, which is
    the ceiling this test pins. The floor, that nothing is requested before
    the yes, is frontend/e2e/privacy.spec.ts and not this file."""
    policy = _headers().get("Content-Security-Policy", "")
    directives = {
        part.strip().split(" ", 1)[0]: part.strip().split(" ", 1)[1]
        for part in policy.split(";")
        if " " in part.strip()
    }
    assert "https://www.googletagmanager.com" in directives["script-src"]
    assert "https://*.google-analytics.com" in directives["connect-src"]
    assert "https://*.analytics.google.com" in directives["connect-src"]
    assert "https://*.google-analytics.com" in directives["img-src"]
    for host in ("doubleclick", "googlesyndication", "googleadservices"):
        assert host not in policy, f"the policy lets an ads host through: {host}"
    # Tag Manager's script host is the same as gtag's, so the container is
    # kept out by the code and not by this header; but a frame or a worker
    # from it would be a different thing and the defaults refuse both.
    assert "frame-src" not in directives
    assert directives["default-src"] == "'self'"


def test_the_pages_carry_hsts_and_not_only_the_api() -> None:
    """prod.py sets SECURE_HSTS_SECONDS and nothing served it to a human.

    Django's SecurityMiddleware stamps that header on responses Django
    produces, and Django produces /api/*. Every page a household opens is the
    exported build handed out by this server, so before this the entire real
    audience received no HSTS at all: the first navigation to
    http://ampeer.nl/ stayed strippable on every visit, not only the first.

    The same blind spot as the four headers above, for the same reason.
    `manage.py check --deploy` reads Django settings, sees the seconds set,
    and does not know this file exists.

    `preload` is deliberately absent, and that assertion is not a style
    preference. The token in the header is what hstspreload.org requires
    before it will accept a submission, from anybody, and removal from the
    list rides browser release trains for months. Its absence at the site root
    is what keeps a submission from being accepted while nobody here has
    decided to make that commitment.
    """
    headers = _headers()
    hsts = headers.get("Strict-Transport-Security")
    assert hsts, (
        "the pages carry no Strict-Transport-Security; prod.py sets it and Django only "
        "ever stamps it on /api/, which no household opens"
    )

    seconds = re.search(r"max-age=(\d+)", hsts)
    assert seconds, f"no max-age in {hsts!r}"
    assert int(seconds.group(1)) >= 31_536_000, (
        f"max-age is {seconds.group(1)}, under a year: a browser that has not visited for "
        "that long is back to a strippable first request"
    )

    assert "includeSubDomains" in hsts, hsts
    assert "preload" not in hsts, (
        f"{hsts!r} carries preload, which is a one way door this project has not chosen to "
        "walk through: anybody may then submit ampeer.nl, and removal takes months"
    )


def test_every_one_of_those_headers_is_unconditional() -> None:
    """Without `always` nginx drops them from any response that is not a 2xx.

    A 404 and a 500 are responses a visitor's browser renders, and an error page
    served without a frame policy is as framable as any other.
    """
    marked = re.findall(r"add_header\s+(\S+)\s+\"[^\"]*\"\s+always\s*;", DIRECTIVES)
    assert set(marked) == set(_headers()), (
        f"{sorted(set(_headers()) - set(marked))} are set without `always`"
    )


def test_the_readiness_endpoint_is_not_served_to_the_internet() -> None:
    """Decision 4 in docs/decisions.md switches the throttle off on
    api/advice/health/, and it is right to: the probe runs every thirty
    seconds and its DRF counter lives in Postgres, so throttling it would turn
    the readiness check into the query it exists to avoid.

    What that decision does not cover is who can reach the route. This file
    proxies all of /api/advice/ to gunicorn, so the one deliberately
    unthrottled endpoint on the service was also reachable from the internet,
    in front of three synchronous workers, and it does real work per request:
    advice/profiles.py stats the profile, opens it and reads a byte.

    The only caller that needs it is not on the internet. infra/api.Dockerfile
    declares the HEALTHCHECK and calls http://127.0.0.1:8000/api/advice/health/
    from inside the api container, which never passes through this server.
    Grepped on 2026-09-01 across .github/workflows/, scripts/ and
    infra/systemd/: no other caller exists.

    An exact match location beats every prefix whatever order they are written
    in, so this cannot be defeated by a later edit reordering the blocks.
    """
    block = re.search(r"location\s+=\s*/api/advice/health/\s*\{([^}]*)\}", DIRECTIVES, re.DOTALL)
    assert block, (
        "no exact match location for /api/advice/health/, so it falls to the /api/advice/ "
        "prefix and the one unthrottled endpoint is proxied to gunicorn from the internet"
    )
    body = block.group(1)
    assert "proxy_pass" not in body, f"the readiness route is still proxied: {body!r}"

    refusal = re.search(r"return\s+(\d{3})", body)
    assert refusal, f"the block refuses nothing: {body!r}"
    assert refusal.group(1)[0] == "4", (
        f"the readiness route answers {refusal.group(1)}, which is not a refusal"
    )


def _throttle_rate_per_second(rate: str) -> float:
    """DRF's "20/hour" as requests per second.

    DRF reads only the first character of the period, so `h`, `hour` and `hr`
    are one thing to it and one thing here.
    """
    count, _, period = rate.partition("/")
    return int(count) / {"s": 1, "m": 60, "h": 3600, "d": 86400}[period[0]]


def test_something_ahead_of_django_limits_the_rate() -> None:
    """DRF's throttle is the per visitor half, and there was no other half.

    Every limit on this service was keyed on the caller, so the cost of one
    more caller is one more full budget, and the counter itself is a Postgres
    round trip in production: reaching the limit is work the database does.
    OWASP ASVS v5.0.0 2.1.3 asks for documented limits "including both
    per-user and globally", and `grep -rnE "limit_req|limit_conn" infra/`
    returned nothing at all on 2026-09-01.

    The ceiling is asserted against what DRF hands one visitor rather than
    written down twice, so raising a DRF rate past the global ceiling fails
    here instead of quietly making nginx the thing real visitors hit.
    """
    from django.conf import settings

    zone = re.search(
        r"limit_req_zone\s+(\S+)\s+zone=(\w+):\d+[kKmM]\s+rate=(\d+)r/([sm])\s*;", DIRECTIVES
    )
    assert zone, "no limit_req_zone: the only limit on this service is DRF's per visitor one"
    key, name, count, unit = zone.group(1), zone.group(2), int(zone.group(3)), zone.group(4)
    ceiling = count / (1 if unit == "s" else 60)

    # A zone keyed on the caller is the half DRF already has, and on this
    # deployment it would key on the wrong thing anyway: nothing reaches this
    # container except through the tunnel, so every request carries the
    # connector's container address, and the visitor's own address is only in
    # the header the caller controls.
    assert key not in {
        "$binary_remote_addr",
        "$remote_addr",
        "$http_x_forwarded_for",
        "$proxy_add_x_forwarded_for",
    }, f"the zone is keyed on {key}, which makes it a second per caller limit, not a global one"

    if key == "$server_name":
        # nginx does not limit at all when the key evaluates empty, silently.
        # This is the one way the directive above can be present and do
        # nothing, so it is the one worth an assertion.
        names = [name.strip() for name in re.findall(r"server_name\s+([^;]+);", DIRECTIVES)]
        assert names and all(names), (
            f"the zone is keyed on $server_name and server_name is {names}: nginx skips "
            "limiting entirely for an empty key, so the limit would be there and off"
        )

    applied = re.findall(r"limit_req\s+zone=(\w+)[^;]*;", DIRECTIVES)
    assert applied, f"zone {name!r} is declared and nothing uses it"
    assert set(applied) == {name}, f"a limit_req names a zone not declared here: {applied}"

    proxying = [body for body in _blocks("location") if "proxy_pass" in body]
    assert proxying, "no location proxies anything, so this test is reading nothing"
    for body in proxying:
        assert re.search(r"limit_req\s+zone=", body), (
            "a location proxies to the API and carries no limit_req of its own. Sibling "
            "locations do not inherit from one another and longest prefix wins, so a "
            "limit_req on /api/ alone leaves /api/advice/ unlimited: " + " ".join(body.split())[:80]
        )

    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    per_visitor = sum(_throttle_rate_per_second(rate) for rate in rates.values())
    assert per_visitor > 0, rates
    assert ceiling >= 50 * per_visitor, (
        f"the global ceiling is {ceiling} r/s and DRF hands one visitor {per_visitor:.4f} r/s, "
        f"so {ceiling / per_visitor:.0f} visitors at their full allowance reach it. That is "
        "not comfortably above legitimate use."
    )


def test_no_location_block_sets_a_header_of_its_own() -> None:
    """The rule this file states about itself, with nothing enforcing it.

    nginx header inheritance is all or nothing: a location that sets one
    add_header of its own loses every add_header from the block above it. The
    comment over /_next/static/ knows this and says it chose `expires` for that
    reason. A later location that adds a Cache-Control or a CORS header the
    ordinary way would silently strip all four security headers from whatever it
    serves, and the config would still be valid and still start.
    """
    offenders = [body.strip()[:60] for body in _blocks("location") if "add_header" in body]
    assert not offenders, (
        "a location sets its own add_header, which drops every security header set above it: "
        + "; ".join(offenders)
    )


def test_the_header_block_and_the_location_scan_both_found_something() -> None:
    """The floor under two checks that are statements over sets built here.

    An empty header map agrees with an empty `always` list, and a location scan
    that matches no block reports no offender.
    """
    assert len(_headers()) >= 4, f"only {sorted(_headers())} parsed out of the config"
    locations = _blocks("location")
    assert len(locations) >= 4, f"only {len(locations)} location blocks were found"
    assert any("proxy_pass" in body for body in locations), (
        "no location proxies anything, so the block matcher is not reading this file"
    )
