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
- [x] Publish authorized GitHub repository and Render Free service.
- [x] Verify public HTTPS and live conversions before marking deployed.
- [x] Document current student-domain redemption and DNS steps; actual redemption remains pending access.

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

## Public deployment verification

10 November 2026: initial source commit e11faf0425e37bb39369c1297629df371f3b9c10 deployed through Render MCP to Uday's confirmed workspace, Free plan, Singapore. Service srv-dbpc560m7kps73agkah0, deploy dep-dbpc56gm7kps73agkbsg reached `live`.

Verified URL: https://free-all-in-converter.onrender.com
Repository: https://github.com/uday-payghon/free-all-in-converter

Public smoke gate passed: PNG→JPG 564 bytes; PDF→DOCX 36,597 bytes; PDF→PDF 1,375 bytes; DOCX→PDF 12,090 bytes; MP4→MP3 21,986 bytes; MP4→WebM 16,607 bytes. Output parsers/decoders, attachment headers, actual bytes, homepage, capabilities and malformed-file error all passed with TLS verification enabled.

Initial remote CI passed backend, dependency audit, production Docker build and HTTP smoke but failed browser installation because `ubuntu-latest` resolved to Ubuntu 26.04 unsupported by this Playwright version. Pinned CI to Ubuntu 24.04. Raw CDP touch drag followed immediately by a tap suppressed Chromium's click; added image decode wait and a 400 ms gesture boundary. Three repeated touch tests then passed.

Public Chromium regression: **10/10 passed in 1.0 minute**, covering all five categories, attachment downloads, image pixel checks, keyboard crop, pointer crop, mobile touch crop, size impossibility, scanned-PDF OCR message, category focus trap, responsive widths and axe checks. The final local touch gesture test also passed 3/3 consecutive runs.

Remote browser CI passed 27 checks but exposed suppression of the Apply tap when mixing raw CDP touch IDs with Playwright's separate touchscreen controller. The touch test now verifies the actual touch rectangle, then activates Apply through the keyboard. Pointer and ordinary UI activation remain covered independently. The fix changes only the test driver, not deployed conversion behavior.

## Final browser result

Pinned Playwright 1.58.2 Noble container, against the 512 MiB production container: **28 passed, 2 expected skips, 1.7 minutes**. Chromium/Firefox/WebKit all passed category dialogs, accessible forms, crop pointer mapping, keyboard crop, ratio controls, real downloads for every category, impossible-size errors and OCR messages. Chromium raw touch selection followed by keyboard Apply passed. Only the CDP-specific touch test is skipped in Firefox/WebKit.

CI browser execution now uses the same pinned Playwright container. A superseded GitHub run was cancelled while its native browser step remained pending.

GitHub run 42775303573 passed **106 backend tests and 28 browser tests (2 expected skips)** plus dependency audit, production Docker and real HTTP smoke. The run failed only while uploading a Firefox download artifact created with root-only permissions inside the browser container. Added a narrowly scoped readability step for synthetic test output directories before artifact upload.
