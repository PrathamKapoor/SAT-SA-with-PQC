# Container image scan: findings and decisions

Scanner: Trivy 0.74.0 (pinned by digest in `.github/workflows/ci.yml`, job
`image-scan`), vulnerability scanner only. Evidence: CI run 36526326909 at
commit `00473a4`; every HIGH and CRITICAL finding is printed as a check
annotation and in the job summary by `deploy/summarize_trivy.py`, and the JSON
reports are kept in the `image-scan-report` artifact.

## What is scanned

| Scanned image | Used by production Compose as |
|---|---|
| `satsa-backend` (built from `Dockerfile`) | `api`, `worker`, `migrate`, `key-init` (one image) |
| `satsa-web` (built from `web/Dockerfile`) | `web` |
| `postgres:17-alpine` | `database` |
| `caddy:2` | `caddy` |
| `chrislusf/seaweedfs:4.47` | bundled object store (optional overlay) |
| `alpine:3` | helper image |

Gate: the job fails on any **fixable CRITICAL** finding in the two SAT-SA
images. HIGH findings and upstream images are reported, not gated, because
fixes for upstream images arrive only when upstream rebuilds; the report is
what makes them visible.

## Changes made because of the scan

| Finding | Image | Action | Result |
|---|---|---|---|
| 3 CRITICAL `perl-base`, 1 CRITICAL `zlib1g` (CVE-2023-45853) and more HIGH, no fix in Debian 12 | `satsa-web` | base image moved from Debian 12 to Debian 13 (`node:24.21.0-trixie-slim`, same Node version) | 0 CRITICAL (run 36525550714) |
| HIGH `msgpack 1.1.2` (fix 1.2.1), HIGH `setuptools 70.3.0` (fix 78.1.1) | `satsa-backend` | Both were pip 26.2.1's *vendored* copies from the base image (`pip/_vendor/msgpack`, `pip/_vendor/pkg_resources`); 26.2.1 is the newest pip, so upgrading cannot fix them. Nothing in the container runs pip (checked `satsa/`, `qsmlops/`, `scripts/`, `deploy/`, CI jobs), so pip is removed from the runtime image | 0 library findings, 0 fixable findings (run 36526326909) |

## Current state (run 36526326909)

| Image | CRITICAL | HIGH | Fixable | Decision |
|---|---|---|---|---|
| satsa-backend | 0 | 44 | 0 | accepted, below |
| satsa-web | 0 | 43 | 0 | accepted, below |
| postgres:17-alpine | 1 | 21 | yes (Go toolchain) | accepted, upstream-blocked |
| caddy:2 | 0 | 17 | yes (Go toolchain, x/crypto, x/net, x/text, grpc) | accepted, upstream-blocked |
| chrislusf/seaweedfs:4.47 | 0 | 1 | yes (grpc) | accepted, upstream-blocked |
| alpine:3 | 0 | 0 | | none |

Nothing here means the stack is vulnerability-free; it means the above list is
complete for HIGH and CRITICAL and every entry has a decision.

### satsa-backend and satsa-web: 8 distinct CVEs, all Debian 13, none fixed in Debian

Both images show the same 8 CVEs (the web image adds no others). Descriptions
are from the Debian security tracker.

| CVE | Packages | What it is | Reachable in SAT-SA? | Decision |
|---|---|---|---|---|
| CVE-2026-76642, -78408, -78409, -78410 | util-linux family (`mount`, `login`, `bsdutils`, `libmount1`, `libblkid1`, `libuuid1`, `libsmartcols1`, `liblastlog2-2`, `util-linux`) | Local privilege escalation through `mount` helpers/fstab options and `nsenter --join-cgroup` | No. Requires an attacker who already runs a process in the container and can invoke `mount`/`nsenter` with privilege. Application code never calls them (no `subprocess`, `os.system`, `Popen` in `satsa/` or `qsmlops/`; no `child_process` in `web/`). Containers run as non-root, production Compose sets `cap_drop: ALL` and `no-new-privileges` on API, worker and web, which removes CAP_SYS_ADMIN and the setuid path these bugs need. | ACCEPTED RISK |
| CVE-2025-69720 | `ncurses-*`, `libtinfo6`, `libncursesw6` | Stack overflow in the `infocmp` command-line tool | No. `infocmp` is never run; libraries are present only as Debian base dependencies. | NOT APPLICABLE (tool not invoked), retained because ncurses is a base dependency |
| CVE-2026-16742 | `libsystemd0`, `libudev1` | Privilege escalation in `systemd-homed` | No. No systemd runs in a container. Libraries are base dependencies only. | NOT APPLICABLE |
| CVE-2026-54369 | `libacl1` | Symlink traversal in libacl path functions when a *privileged* caller processes attacker-controlled paths | No. No privileged process in the container uses libacl on user-controlled paths; the app runs unprivileged. | ACCEPTED RISK |
| CVE-2026-9538 | `perl-base` | Memory exhaustion in Perl `Archive::Tar` on a crafted tar header | No. Perl is not run by the application; `perl-base` is a Debian-essential package that cannot be removed. | NOT APPLICABLE (interpreter not invoked) |

"Not reachable" is established from the code search above and the container
configuration, not from a reachability analysis by the scanner. These entries
must be revisited if the application ever shells out or the container
capabilities change. They clear on their own when Debian ships fixes and the
CI build (`docker build --pull`) picks them up.

### Upstream images (not built by SAT-SA)

| Image | Finding | Where | Runtime relevance | Decision |
|---|---|---|---|---|
| postgres:17-alpine | 1 CRITICAL (CVE-2025-68121) and 21 HIGH, all "stdlib v1.24.6" | Only the `gosu` 1.19 entrypoint helper (built with go1.24.6). PostgreSQL itself is C and is not implicated. | `gosu` runs once at container start to drop privileges and makes no network calls; the database is not reachable from outside the Compose network. Fix requires upstream to rebuild `gosu`; the tag pulled on the scan date (created 2026-09-17) still contains it. | ACCEPTED RISK (upstream-blocked) |
| caddy:2 | 17 HIGH: Go stdlib 1.26.3 (fixed in 1.26.6), `x/crypto` 0.52.0, `x/net` 0.55.0, `x/text` 0.37.0, `grpc` 1.81.0 | The Caddy binary (go1.26.3, upstream image created 2026-09-17, the newest published) | **Relevant.** Caddy is the only internet-facing container. I did not assess each stdlib CVE for reachability. No newer upstream image exists to move to. | ACCEPTED RISK (upstream-blocked). Operators must re-pull (`docker compose pull caddy`) when upstream republishes; the CI report shows when it does. Building a patched Caddy with xcaddy was considered and not done: it makes SAT-SA responsible for the proxy's patch cadence. |
| chrislusf/seaweedfs:4.47 | 1 HIGH (grpc) | SeaweedFS binary | Optional bundled store, internal network only. Real deployments on AWS should use S3 instead. | ACCEPTED RISK (upstream-blocked) |

## Integrity of the scan job

- The two SAT-SA images are built from the same contexts and Dockerfiles as
  `deploy/compose.production.yml`; the upstream images are the exact tags the
  Compose files reference.
- The gate is `--severity CRITICAL --ignore-unfixed --exit-code 1`: it ignores
  only findings that have no fix yet. No `.trivyignore`, no `--skip-*`, no
  `continue-on-error`.
- HIGH findings are listed, not gated. That is a policy choice, recorded here;
  tightening it to fail on fixable HIGH is possible once upstream images are
  patched.
- The report is preserved as the `image-scan-report` artifact and as check
  annotations on every run.
