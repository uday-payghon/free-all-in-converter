# Security and privacy status

This release is a bounded public prototype, not a hardened multi-tenant conversion service.

Implemented and tested:

- No account, password, payment, database, external URL input or permanent download store.
- Request-scoped temporary files; cleanup on normal download, conversion errors, deadlines and failed transfers. A machine/container crash can leave temporary data until the ephemeral filesystem is cleared. Download responses use `Cache-Control: no-store`.
- Multipart request bytes limited before parser completion, uploaded file bytes separately limited; three active requests maximum, one conversion, five-second queue wait, upload idle timeout 30 seconds / upload total 120 seconds.
- Twelve conversion attempts per minute per peer by default. In-memory counters use salted hashes, a bounded 4096-entry map and expire logically after one minute. They reset when the process restarts. This is not a distributed limiter.
- No forwarded IP is trusted by default. `TRUSTED_PROXY_CIDRS` accepts explicit verified ingress networks; X-Forwarded-For is walked right-to-left only for a trusted immediate peer. Never set wildcard /0 networks. Until ingress is verified, people behind the same proxy share its quota.
- Pillow decodes only the advertised image types and compares detected type to extension. Pixel bounds precede decoding. Media probes allow only supported demuxers and file/pipe protocols; no playlist/network demuxers. PDFs require a valid unencrypted 1–80-page document. Office archives have expansion/member limits and reject VBA/embedded objects and linked external resources in common OOXML/ODF relationships. Legacy Office, RTF and all complex file formats still need stronger isolation.
- Native commands use argument arrays, no shell interpolation. Converter stderr and server paths are not returned. Ghostscript uses SAFER; LibreOffice uses a unique profile with macro execution disabled.
- Each conversion, including image/PDF parsing, runs in a disposable child process. The entire process group is killed on cancellation, completion or the 240-second deadline. Linux worker limits: 240 CPU seconds, 1 GiB virtual address space, 512 MiB per output file, 128 open file descriptors. These are resource bounds, not a security sandbox.
- Non-root production image. Local release verification additionally uses read-only root, dropped Linux capabilities, no-new-privileges, 512 MiB container RAM, one CPU, 128 processes and bounded temporary mounts. Render Blueprint does not expose all those Docker run flags; do not assume they are enforced there.
- CSP, anti-framing, nosniff, no-referrer and permissions-policy headers. No third-party fonts, analytics or browser requests. Uvicorn access logs are disabled. Application success logs contain category and elapsed processing time, never filenames, file content or IP addresses. Hosting providers may independently log connection metadata.
- Python dependencies pinned including transitive constraints; recorded pip-audit found no known advisories at the time of verification. This does not prove absence of vulnerabilities. Re-audit and rebuild regularly.

Before an unrestricted or high-traffic production launch:

1. Add malware scanning with maintained signatures and fail-closed handling, on compute with adequate RAM.
2. Move each untrusted job to an isolated sandbox with no network access and no access to other jobs or service secrets. Current jobs share a Unix account and container network; protocol checks and macro settings do not eliminate parser exploits or every external-document reference.
3. Configure verified proxy identities and a distributed edge limiter/WAF, abuse reporting, monitoring and service quotas. Add a durable queue if scaling beyond one process.
4. Validate large, hostile and complex files under realistic traffic and resource limits. A 40 MB compressed file can need far more than 512 MB to decode. Samples tested here do not establish a capacity guarantee.
5. Publish operator contact/retention terms and review provider logging policies. Choose appropriate paid compute for an always-on service.

No claim of malware scanning, complete subprocess sandboxing, physical-device accessibility certification or public deployment is made by this repository.
