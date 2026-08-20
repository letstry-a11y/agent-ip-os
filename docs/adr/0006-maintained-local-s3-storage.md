# ADR 0006: use maintained Garage for local S3-compatible storage

- Status: Accepted
- Date: 2026-08-20
- Scope: M0-05 local development only

## Context

The accepted baseline names MinIO as the local S3-compatible store. The open-source
`minio/minio` repository and image are now archived, and the upstream security advisory
[GHSA-xh8f-g2qw-gcm7](https://github.com/minio/minio/security/advisories/GHSA-xh8f-g2qw-gcm7)
states that all final open-source releases are affected. The maintained AIStor successor
requires a separate license. Committing a known-vulnerable image or silently accepting a
license is not an acceptable M0 default.

Garage is a maintained, open-source S3-compatible object store. Its official quick-start
documents a single-node development mode and explicitly warns that the mode has no data
redundancy and must not be used for production.

## Decision

Use `dxflrs/garage:v2.3.0` in single-node mode for the M0-05 local Compose stack. Keep the
application boundary S3-compatible so this development dependency does not select a
production storage vendor. Generate local access and internal credentials at first startup
under ignored `.runtime/`; bind its S3 port to loopback only.

## Consequences

- The local stack avoids an archived image with a known unresolved vulnerability.
- M0-05 differs from the baseline's named local product but preserves its S3-compatible
  architectural contract.
- Garage single-node data has no redundancy. It is test data, not a backup or production
  system.
- Production object storage remains an explicit later deployment decision and must not
  inherit local credentials or topology.
