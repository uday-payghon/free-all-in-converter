# Codex master prompt: Free All-in Converter

You are the lead full-stack engineer, product designer, QA engineer, and release engineer for **Free All-in Converter**. Take the existing repository as your starting point. **Do not rewrite a working feature without a compelling reason.** Ship a reliable, beautiful, free-to-use web converter, including source, automated tests, and a verified deployment checklist. Never claim a file conversion, production readiness, or deployment succeeded unless it has actually been tested.

## Product and scope

- Public homepage at `/`, completely usable **without login, email, registration, subscription, or payment**.
- Brand: **Free All-in Converter**; tagline **"Your file. Your format. Your size."**
- Design: polished professional utility/product design. Colors: white (#ffffff), red (#dc2228), near-black (#151515), very light grey. Avoid gradient-heavy AI dashboards, neon, glassmorphism, chatbots, floating AI badges and unnecessary complexity.
- Mobile-first and accessible; stable layouts at 320px, 390px, 768px, 1024px, desktop. Keyboard navigation, semantic HTML, focus states, ARIA for dialogs, high contrast, reduced motion, helpful errors, responsive file names and controls.
- Primary CTA **"Start converting"** opens a clear category selector dialog: **Images, Video, Audio, PDF tools, Documents**. Clicking a category reveals a category-specific workspace; do not show irrelevant settings.
- Workflows: choose category → upload/drag/drop one file → choose output format → set width, height, crop and/or file size as relevant → convert → see original/output metadata → download.

## Supported conversion matrix

1. **Images:** inputs JPG/JPEG, PNG, WEBP, GIF, BMP, TIFF; outputs JPG, PNG, WEBP, BMP, TIFF. Provide image preview; freehand drag-to-select crop area (mapped accurately to source pixels), reset/apply buttons; width and height fields in pixels; optional lock aspect ratio; fit inside / crop fill / pad fill / stretch exact; optional maximum KB or MB target; transparencies handled correctly (white background for JPEG); preserve EXIF orientation; handle very large images safely. **Three constraints rule:** WIDTH × HEIGHT + MAX FILE SIZE; never silently change fixed dimensions to meet tiny file limits. Display source dimensions/file size, selected crop dimensions, requested output dimensions and size cap. If target is impossible, tell the user which parameter to relax.
2. **Video:** inputs MP4, WEBM, MOV, MKV, AVI → outputs MP4, WEBM; optional max resolution and file size. FFmpeg with safe subprocess calls, quality controls, timeout and useful error messages.
3. **Audio:** input audio MP3, WAV, M4A, OGG, FLAC, AAC, WMA or a user-uploaded video; outputs MP3, WAV, M4A, OGG. Support extracting MP3 from their own uploaded video and setting a max KB/MB size by selecting bitrate. Never implement downloading unauthorized songs from streaming platforms; only transform user-supplied files. Clearly warn when a specified size is impossible.
4. **PDF:** PDF → PDF compression and PDF → editable DOCX for text-based PDFs. The MVP implementation extracts selectable text and may not reproduce complex layout, tables, columns or images accurately. Detect scanned/image-only PDFs and show an explicit 'requires OCR' message. Add OCR as a separate milestone, not an untruthful existing feature.
5. **Documents:** DOC, DOCX, PPT, PPTX, XLS, XLSX, RTF, TXT, ODT, ODP, ODS → PDF via LibreOffice. Never claim the reverse conversions work unless implemented and tested.

## Architecture and API

- Keep the existing single-service architecture: Python FastAPI (HTTP API), plain HTML/CSS/JS (browser), Pillow (images), FFmpeg + ffprobe (audio/video), Ghostscript (PDF compression), pypdf + python-docx (text-based PDF→DOCX), headless LibreOffice (Office→PDF).
- Keep `GET /health`, `GET /api/capabilities`, `POST /api/convert`. Accept one multipart file; validate category/output combination, extension, file size (default 80 MB), image dimensions (1–8192 px; video width 64–8192 px), and four crop coordinates if provided. Reject invalid combinations with HTTP 422 and descriptive messages.
- No database needed; do not store user accounts or permanent uploads. Use unique temporary directories and cleanup after the download completes or processing fails. Non-root Docker runtime. Limit concurrency and conversion timeout.
- Implement production hardening before high public traffic: per-IP/user rate limits via trusted proxy configuration, content sniffing, malware scanning, subprocess sandboxing, CPU/memory/time quotas, request body limits, anonymized operational logs, abuse detection, and privacy disclosures. Do not trust user input or pass unsanitized strings into a shell.
- Size controls are **maximum targets, not guarantees of exact byte counts**. PNG/TIFF/BMP do not compress like JPEG/WebP; do not mislead users about exact sizing. Show the actual final bytes.

## Visual and interaction requirements

- Header: memorable red brand mark, compact navigation (All tools, How it works, FAQ), high-contrast Convert button.
- Hero: expressive editorial typography "Every file. Exactly how you need it." with red emphasis; restrained conversion-demo card on the right; no stock-robot visuals; no made-up analytics or testimonials.
- Category cards: five options, concise supported format labels, icons, hover/focus affordances; same options inside an accessible category dialog.
- Workspace: two-column desktop layout (upload left, settings right), single-column mobile. Image preview thumbnail and full crop dialog. Persistent live summary: original filename/size, output extension, pixel size, target KB/MB. Progressive feedback and a clear download result state.
- Footer, concise help text, FAQ addressing size-limit feasibility, scanned PDF OCR limitations and privacy.
- Buttons, crop, keyboard interactions, drag-and-drop and downloaded filenames must work, not be decorative.

## Quality assurance and release

1. Inspect repository before modifying it. Produce an implementation checklist; then implement it, rather than only drafting a plan.
2. Run and extend automated tests: image crop geometry, 3 constraints, invalid upload, PNG alpha, aspect ratio, PDF→DOCX, DOCX→PDF, audio extraction, video conversion, target feasibility. Preserve existing passing tests.
3. Verify the actual browser UI at desktop and mobile widths: no horizontal overflow, modal category selection, crop via pointer/touch, submit/error/success flows, downloading.
4. Ship `Dockerfile`, `render.yaml`, `.dockerignore`, `.gitignore`, `README.md`, `DEPLOYMENT.md`, requirements and scripts.
5. Prefer a **single Docker deployment to Render** for the first prototype (no database). Respect Render Free's sleeps and limits. When a provider account is available, deploy and return the verified public URL. If a provider account or repo creation permission is unavailable, stop at a reproducible deployable package and state exactly what is missing; never fabricate a live URL.
6. Github Student Developer Pack: point to current official Namecheap (.me), Name.com (select TLD), or .TECH (1-year) options, always warn about availability and renewal fees. If Firebase is used, host static frontend separately and deploy Python media compute elsewhere; Spark Hosting cannot execute FFmpeg/LibreOffice.
7. Finish with a concise report containing actual test results, supported features, known limitations, deployment status, and concrete next steps.

## Order of work

**Phase A:** polish and validate existing UI and conversion API. **Phase B:** browser interaction tests, file validations and abuse controls. **Phase C:** accessibility and performance improvements. **Phase D:** Docker smoke test, GitHub repository publishing if authorized, then Render deployment when connected. **Phase E:** link student domain and add optional advanced format converters only after passing tests.

**Definition of done:** Users can open one public website, choose a category, convert an allowed file with their specified dimensions/size when feasible, and download the result without logging in. Public deployment is called complete **only** with a verified working link and live conversion smoke test.
