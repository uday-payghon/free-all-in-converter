# Release audit — 10 November 2026

## Initial audit (before changes)

Read CODEX_PROMPT.md, README.md, DEPLOYMENT.md, both Python modules, all frontend source, tests and deployment configuration completely. The starting folder has no Git history. Preserve existing UI and conversion architecture.

Findings: upload bound runs after multipart parsing; unbounded waiting jobs; extension-only validation; image pixel check after decoding; raw converter stderr exposed; no whole-job deadline for Pillow/PDF; no security headers; missing modal focus trap and keyboard crop; reset crop leaves stale summary; controls can change while a conversion is pending; hard-coded upload cap; exact 1 KB rejected; odd video dimensions can fail; PDF compression can enlarge files; no real browser automation or Docker CI.

## Implementation checklist

- [x] Establish baseline backend tests in Docker.
- [x] Bound incoming bodies/jobs; validate actual contents; add safe converter errors, deadlines, subprocess limits and cleanup.
- [x] Preserve geometry, transparency and size targets; exercise all advertised input/output families.
- [x] Fix modal focus, keyboard crop, contrast, mobile overflow and conversion state races.
- [x] Test Chromium, Firefox and WebKit, downloads, errors and accessibility.
- [x] Build and smoke-test non-root production Docker image with constrained resources.
- [x] Record dependency audit and residual security/format limitations.
- [ ] Prepare GitHub/Render package; publish only when repository creation is authorized and Render access is available.
- [ ] Verify public HTTPS and live conversions before marking deployed.
- [ ] Document current student-domain redemption and DNS steps.

## Verified local release results

- Baseline: 18/18 backend tests passed before edits. Final: 106/106 backend tests passed in 41.38 seconds under 512 MiB / one CPU. One upstream TestClient deprecation warning.
- All advertised image inputs and outputs, media input families, video outputs, audio outputs, and all eleven document extensions tested using real encoders and readable outputs.
- Chromium, Firefox and WebKit Linux browser suite: 27 passed, one touch timing assertion failed, two intentionally skipped Chromium-only CDP tests. After fixing event pacing and waiting for crop state, the touch test passed separately. Full final rerun recorded below when complete. No axe WCAG A/AA violations in passing homepage, dialog, workspace and result checks.
- Six real HTTP smoke conversions passed on the constrained production image: PNG→JPG, PDF→DOCX, PDF→PDF, DOCX→PDF, MP4→MP3, MP4→WebM. Health, capabilities, attachment filenames, actual bytes, decoding and malformed-file error verified.
- Runtime UID 10001, Docker health healthy, no remaining request temp directories after smoke tests.
- Python pip-audit: no known vulnerabilities with patched locked runtime dependencies. npm audit: zero advisories. Native Debian packages are not included in pip-audit.
- Local compressed homepage/CSS/JS approximately 17 KB transferred combined. Measured DOMContentLoaded approximately 60 ms on localhost; this is not a public-network performance guarantee. No third-party resource requests.
- Reviewed desktop, 390 px mobile and crop-editor screenshots. Browser overflow assertions cover 320/390/768/1024/1440 px. Physical Safari/iOS/Android devices and assistive-technology testing remain unverified.

## Deployment

User authorized new public GitHub repository and Render Free deployment to Uday's workspace on 10 November 2026. Publication and live deployment verification are in progress. Student eligibility and domain redemption are not yet verified.
