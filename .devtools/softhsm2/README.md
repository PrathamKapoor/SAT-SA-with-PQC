# A1.2 development PKCS#11 provider bootstrap

This directory holds the SoftHSM2 portable installation used to certify the
real PKCS#11 provider path during workstream A1.2.

## What is here

- `softhsm2/README.txt` — vendor-supplied readme from the DISIG SoftHSM2-Windows
  portable archive (DISIG is a recognized PKI/smart-card vendor; the archive is a
  Windows packaging of upstream SoftHSMv2 2.5.0).
- `softhsm2/bin/`, `softhsm2/lib/`, `softhsm2/share/doc/` — gitignored.  Populate
  them by running the bootstrap script below.
- `softhsm2/etc/` — checked in: an example `softhsm2.conf` that points at the
  isolated development token directory under `%TEMP%\qsmlops-a12-tokens`.

## Reproducing the environment

```powershell
# Run once from the repo root
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_softhsm2.ps1
```

This downloads `SoftHSM2-2.5.0-portable.zip` from
`https://github.com/disig/SoftHSM2-for-Windows/releases/tag/v2.5.0`, verifies
the archive against the GitHub release manifest, and extracts it under
`.devtools/softhsm2/`.

## Token provisioning (one-time, ephemeral)

The real-provider test harness (`tests/test_hsm_a12_real_provider.py`) expects:

1. The `SOFTHSM2_CONF` environment variable to point at a configuration file
   that stores tokens outside the repository (the default is
   `%TEMP%\qsmlops-a12-softhsm2.conf`).
2. An initialized token with label `qsmlops-a12-dev` and an ephemeral user PIN
   stored in `%TEMP%\qsmlops-a12-pins.env`.

The test module will skip every test with a precise reason if either prerequisite
is missing; it never falls back to mocks silently.

To initialize a fresh development token manually:

```bash
SO_PIN=$(python -c 'import secrets; print(secrets.token_hex(8))')
USER_PIN=$(python -c 'import secrets; print(secrets.token_hex(8))')
mkdir -p "$(cygpath -u "$TEMP")/qsmlops-a12-tokens"
cat > "$(cygpath -u "$TEMP")/qsmlops-a12-softhsm2.conf" <<EOF
directories.tokendir = $(cygpath -w "$TEMP/qsmlops-a12-tokens")
objectstore.backend = file
objectstore.umask = 0077
log.level = ERROR
slots.removable = false
modules.dir = $(cygpath -w "$PWD/.devtools/softhsm2/lib")
EOF
printf 'SO=%s\nUSER=%s\n' "$SO_PIN" "$USER_PIN" > "$(cygpath -u "$TEMP")/qsmlops-a12-pins.env"
SOFTHSM2_CONF="$(cygpath -w "$TEMP/qsmlops-a12-softhsm2.conf")" \
  "$PWD/.devtools/softhsm2/bin/softhsm2-util.exe" \
  --module "$PWD/.devtools/softhsm2/lib/softhsm2.dll" \
  --init-token --free --label "qsmlops-a12-dev" \
  --so-pin "$SO_PIN" --pin "$USER_PIN"
```

> Note: `softhsm2-util.exe` is the 32-bit executable, so it loads the 32-bit
> `softhsm2.dll`.  python-pkcs11 (which is 64-bit under Python 3.13 on Windows)
> loads the 64-bit `softhsm2-x64.dll`.  Both come from the same archive.

## Secret hygiene

The PIN file lives in `%TEMP%` (never in the repo) and is gitignored
implicitly because the repository has no PIN files checked in.  Tests must
never embed or log credentials.
