# Dockerized PDS

This fork follows [bluesky-social/pds](https://github.com/bluesky-social/pds)
and adds in-container `pds-*` administration commands. It currently bundles
`@atproto/pds` 0.5.34 (distro 0.4.5034) and Node 24.19, matching upstream
commit `7cccef654a9d94d935deba1ee62490b316549ef6`.

## Running the container

1. Copy `sample.env` to a local `pds.env`, restrict its permissions to 0600,
   and supply your hostname and generated secrets. `pds.env` is intentionally
   ignored by Git and excluded from Docker builds.
2. Adjust `docker-compose.yaml` for your host and reverse proxy. Production
   deployments should use an immutable `sha-<commit>@sha256:<index-digest>`
   image reference. Pin the multi-platform index when deploying to ARM64.
3. Run `docker compose -f docker-compose.yaml up -d`.

The service stores persistent data under `/pds`; the example binds that to
`./pds/data`. Administration commands read the same runtime secrets through
`PDS_ENV_FILE=/config/pds.env`. Preserve both bind mounts when upgrading.

## Administration

The image retains the fork's `pds-account`, `pds-create-invite-code`,
`pds-request-crawl`, and `pds-help` commands, alongside upstream's `goat` CLI.
For example:

```sh
docker exec -it pds pds-account list
docker exec -it pds pds-create-invite-code
```

Account creation prints a generated password; run it in a private terminal,
not a CI job. See the upstream documentation for federation, SMTP, and account
migration. The upstream host installer is deliberately absent from this fork;
our container deployment does not install a host-level PDS distribution.

## Updating and verification

Merge an explicitly reviewed upstream commit, retaining the in-image admin
commands and runtime environment-file mount. Take a consistent backup of all
PDS databases and blobs before deploying an upgrade: a container downgrade
alone cannot undo database migrations. Follow [PUBLISH.md](PUBLISH.md) for the
upstream package-to-distro version mapping.

Pull requests build an image, inspect every final-image layer for checkout
metadata and environment files, and start an isolated PDS with disposable
storage. Main publishes amd64 and arm64 images only after that smoke test passes.
Both checkout paths disable persisted Git credentials; `.dockerignore` restricts
the build context to service code and administration scripts. Live deployment
remains a separate reviewed digest update in clamsible.

The weekly `upstream-version` workflow compares the bundled dependency with
upstream's declared PDS version and fails on drift. It reports an update need;
it never upgrades a live service automatically. After deployment, verify
`/xrpc/_health`, an authenticated admin read, rate-limit response headers,
and the existing account's repository/federation access.

The previously committed `pds.env` was removed from the current tree. Its
admin, JWT, and PLC rotation credentials were checked against the current
production vault and do not match. Historical Git revisions still contain
that retired file; never reuse those values.
