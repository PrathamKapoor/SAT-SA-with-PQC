#!/usr/bin/env python3
"""HTTP security smoke against a running SAT-SA site (standard library only).

This is an automated configuration check of the public entry point, not a
penetration test: response headers and CSP, cache behaviour, HTTP to HTTPS
redirect, that the internal API is not routed publicly, unauthenticated and
invalid-session handling, path traversal, oversized bodies, unknown hosts,
CORS and information leakage in error pages.

    python3 deploy/http_security_check.py https://satsa.example.org
    python3 deploy/http_security_check.py https://localhost --insecure   # local CA

Exit status 0 when every check passes; each failure is printed.
"""

from __future__ import annotations

import argparse
import http.client
import re
import ssl
import sys
from urllib.parse import urlsplit

LEAKS = ("Traceback", "node_modules", "at Object.", "stack trace", "root:x:0:0",
         "module.exports", "SELECT ", "psycopg", "uvicorn", "FastAPI")


class Site:
    def __init__(self, base: str, insecure: bool) -> None:
        parts = urlsplit(base)
        if parts.scheme != "https" or not parts.hostname:
            raise SystemExit("the site URL must be https://host")
        self.host = parts.hostname
        self.port = parts.port or 443
        self.context = ssl.create_default_context()
        if insecure:
            self.context.check_hostname = False
            self.context.verify_mode = ssl.CERT_NONE

    def request(self, method, path, *, headers=None, body=None, host=None, plain=False):
        if plain:
            conn = http.client.HTTPConnection(self.host, 80, timeout=30)
        else:
            conn = http.client.HTTPSConnection(self.host, self.port, timeout=60,
                                               context=self.context)
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        conn.putheader("Host", host or self.host)
        for key, value in (headers or {}).items():
            conn.putheader(key, value)
        if body is not None:
            conn.putheader("Content-Length", str(len(body)))
        conn.endheaders()
        try:
            if body is not None:
                conn.send(body)
            response = conn.getresponse()
            data = response.read(2_000_000)
            return response.status, {k.lower(): v for k, v in response.getheaders()}, data
        except (ConnectionError, http.client.HTTPException, OSError) as exc:
            # Refusing an oversized body by closing the connection is a pass
            # for that check; callers that need a response treat it as failure.
            return 0, {}, str(exc).encode()
        finally:
            conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("url")
    parser.add_argument("--insecure", action="store_true",
                        help="accept a certificate from a local CA (testing only)")
    args = parser.parse_args()
    site = Site(args.url, args.insecure)
    failures: list[str] = []

    def check(name, condition, detail=""):
        print(("PASS " if condition else "FAIL ") + name + (f": {detail}" if detail and not condition else ""))
        if not condition:
            failures.append(name)

    def no_leak(name, body):
        text = body.decode("utf-8", "replace")
        found = [marker for marker in LEAKS if marker in text]
        check(f"{name} discloses no internals", not found, ", ".join(found))

    status, headers, body = site.request("GET", "/login")
    check("login page served over HTTPS", status == 200, str(status))
    expected = {
        "strict-transport-security": "max-age=",
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": "camera=()",
        "cross-origin-opener-policy": "same-origin",
    }
    for header, value in expected.items():
        check(f"header {header}", value in headers.get(header, ""), headers.get(header, "missing"))
    csp = headers.get("content-security-policy", "")
    for directive in ("default-src 'self'", "object-src 'none'", "frame-ancestors 'none'",
                      "base-uri 'self'", "form-action 'self'", "connect-src 'self'"):
        check(f"CSP {directive}", directive in csp, csp or "missing")
    check("dynamic page is not cacheable", "no-store" in headers.get("cache-control", ""),
          headers.get("cache-control", "missing"))
    for header in ("server", "x-powered-by"):
        check(f"no {header} header", header not in headers, headers.get(header, ""))
    check("no wildcard CORS", headers.get("access-control-allow-origin") is None)

    asset = re.search(rb'/_next/static/[^"\'\s>]+\.js', body)
    if asset:
        status, asset_headers, _ = site.request("GET", asset.group(0).decode())
        check("hashed build asset is cacheable",
              status == 200 and "no-store" not in asset_headers.get("cache-control", ""),
              f"{status} {asset_headers.get('cache-control')}")
    else:
        check("login page references build assets", False)

    status, headers, _ = site.request("GET", "/login", plain=True)
    location = headers.get("location", "")
    check("HTTP redirects to HTTPS", status in {301, 302, 307, 308} and location.startswith("https://"),
          f"{status} {location}")

    for path in ("/api/v1/entities", "/api/v1/session", "/health/ready", "/openapi.json", "/docs"):
        status, headers, body = site.request("GET", path)
        check(f"internal API not routed publicly ({path})",
              status in {301, 302, 303, 307, 308, 404}
              and b"openapi" not in body and b'"error"' not in body,
              str(status))

    status, headers, _ = site.request("GET", "/workbench")
    location = headers.get("location", "")
    check("unauthenticated workbench redirects to login",
          status in {302, 303, 307, 308} and location.split("?")[0].endswith("/login"),
          f"{status} {location}")
    check("redirect stays on the public origin",
          location.startswith(("/", f"https://{site.host}")), location)

    status, headers, _ = site.request("GET", "/workbench",
                                      headers={"Cookie": "satsa_session=forged; satsa_org=forged"})
    location = headers.get("location", "")
    check("forged session cookie is not accepted",
          status in {302, 303, 307, 308} and ("/login" in location or "/logout" in location),
          f"{status} {location}")

    for path in ("/..%2f..%2f..%2fetc%2fpasswd", "/_next/static/..%2f..%2f..%2fserver%2fapp%2fpage.js",
                 "/%2e%2e/%2e%2e/etc/passwd", "/login/..%5c..%5cwindows%5cwin.ini"):
        status, _, body = site.request("GET", path)
        check(f"traversal refused ({path})", status in {400, 403, 404} or status in {301, 302, 307, 308},
              str(status))
        no_leak(f"traversal response ({path})", body)

    status, _, body = site.request("GET", "/definitely-not-a-page")
    check("unknown page is 404", status == 404, str(status))
    no_leak("404 page", body)

    oversized = b"x" * (19 * 1024 * 1024)
    status, _, _ = site.request("POST", "/login", body=oversized,
                                headers={"Content-Type": "application/octet-stream"})
    check("oversized request body refused", status in {0, 413}, str(status))

    status, headers, body = site.request("GET", "/login", host="attacker.example")
    check("unknown Host is not served the site", b"SAT-SA" not in body,
          f"{status} {len(body)} bytes")

    status, _, body = site.request("TRACE", "/login", headers={"X-Probe": "reflect-me"})
    check("TRACE does not reflect requests", b"reflect-me" not in body, str(status))

    status, headers, body = site.request(
        "POST", "/login",
        headers={"Origin": "https://attacker.example", "Next-Action": "0" * 40,
                 "Content-Type": "text/plain;charset=UTF-8"},
        body=b"[]",
    )
    check("cross-origin server action issues no session",
          "satsa_session" not in headers.get("set-cookie", ""), str(status))
    check("cross-origin server action gets no CORS grant",
          headers.get("access-control-allow-origin") is None)
    no_leak("cross-origin server action response", body)

    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
