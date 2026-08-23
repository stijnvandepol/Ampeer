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
    assert len(token_free) == 3, token_free
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
    for directive in ("default-src 'self'", "connect-src 'self'", "frame-ancestors 'none'"):
        assert directive in policy, f"the policy no longer carries {directive!r}: {policy!r}"


def test_every_one_of_those_headers_is_unconditional() -> None:
    """Without `always` nginx drops them from any response that is not a 2xx.

    A 404 and a 500 are responses a visitor's browser renders, and an error page
    served without a frame policy is as framable as any other.
    """
    marked = re.findall(r"add_header\s+(\S+)\s+\"[^\"]*\"\s+always\s*;", DIRECTIVES)
    assert set(marked) == set(_headers()), (
        f"{sorted(set(_headers()) - set(marked))} are set without `always`"
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
