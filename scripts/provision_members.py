"""Add organization members through the SAT-SA API and print their credentials.

The same call the workbench's Members page makes (POST /api/v1/members, an
organization administrator's credential). Each new credential is printed once
as JSON on stdout; store it securely and do not commit it.

    python scripts/provision_members.py --api http://api:8000 \
        --credential <admin key_id.secret> --organization <organization id> \
        --member supervisor "Supervisor Name" supervisor@example.org \
        --member analyst "Analyst Name" analyst@example.org
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

ROLES = ("viewer", "analyst", "supervisor", "auditor", "admin")


def invite(
    api: str, credential: str, organization: str, role: str, name: str, email: str
) -> dict:
    request = urllib.request.Request(
        api.rstrip("/") + "/api/v1/members",
        data=json.dumps(
            {"name": name, "email": email, "role": f"satsa_{role}"}
        ).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {credential}",
            "X-Organization-ID": organization,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"adding {email} failed: HTTP {exc.code} {exc.read().decode(errors='replace')}"
        ) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", required=True)
    parser.add_argument(
        "--credential", required=True, help="an organization administrator's credential"
    )
    parser.add_argument("--organization", required=True)
    parser.add_argument(
        "--member",
        nargs=3,
        action="append",
        metavar=("ROLE", "NAME", "EMAIL"),
        required=True,
    )
    args = parser.parse_args(argv)
    issued = {}
    for role, name, email in args.member:
        if role not in ROLES:
            parser.error(f"role must be one of {', '.join(ROLES)}")
        issued[role] = invite(
            args.api, args.credential, args.organization, role, name, email
        )["credential"]
    print(json.dumps(issued))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
