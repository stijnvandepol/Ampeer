"""nginx configuration read as text, because two lines in it decide whether the
product works and whether it keeps a promise the rest of the project enforces.

Nothing here starts nginx. These are properties of the file; Task 6 drives the
running server, and the running server is where the log was actually read
before this file was believed.
"""

from __future__ import annotations

import re
from pathlib import Path

CONF = Path(__file__).resolve().parent.parent / "infra" / "nginx" / "nginx.conf"
TEXT = CONF.read_text(encoding="utf-8")

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
    passes = re.findall(r"proxy_pass\s+([^;]+);", TEXT)
    assert all("api" in target for target in passes), passes
    blocks = re.findall(r"location\s+(\S+)\s*\{([^}]*)\}", TEXT, re.DOTALL)
    proxying = [name for name, body in blocks if "proxy_pass" in body]
    assert all(name.startswith("/api/") for name in proxying), proxying
