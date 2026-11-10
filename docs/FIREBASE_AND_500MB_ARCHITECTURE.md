# Hosting migration and 500 MB support — release proposal

This document is a **migration plan**, not a claim that Firebase, a custom domain, or 500 MB uploads are currently active.

## Current state
- The production converter remains on Render: https://free-all-in-converter.onrender.com/
- The production Docker backend includes Pillow, FFmpeg, Ghostscript and LibreOffice. Firebase Hosting alone does not execute this backend.
- `render.yaml` currently sets `MAX_UPLOAD_MB=40`. Uploading 500 MB is **not** supported on the current public service.
- The old 80 MB message in frontend hint text is synchronized with the API capability limit on load. The API remains authoritative.
- The UI size target (KB/MB) means an upper bound, not a promise of an exact byte-for-byte file size.

## Recommended split

```
free-all-in-converter.web.app / custom domain
    ├── Firebase Hosting: homepage, converter UI, SEO pages, robots.txt, sitemap
    └── API (same origin via rewrite or explicit API base URL)
          ├── issue upload job + authenticated short-lived upload grant
          ├── Cloud Storage: direct/resumable source upload (up to 500 MB)
          ├── async worker: Cloud Run Job or worker service with FFmpeg,
          │                  Pillow, LibreOffice, Ghostscript
          ├── conversion status polling, progress and timeout/cancel states
          └── short-lived signed download URL → automatic cleanup
```

### Why this architecture?
Firebase Hosting improves first-page static delivery, but **does not remove the cold-start issue from a sleeping Render conversion API**. To remove that delay end-to-end, run the API/worker on suitable compute. Google Cloud Run or other compute is separate from Firebase Hosting and may incur charges.

Do not upload 500 MB files through an ordinary FastAPI request to Firebase Hosting/Functions. Use resumable, direct-to-object-storage uploads and an asynchronous conversion job. Set per-user/IP rate limits and abuse protections since there is no login.

### 500 MB implementation gates (must pass before advertised)
1. Cloud billing and quota approved; configure a storage bucket, CORS, lifecycle deletion, and least-privilege worker identity.
2. Create job IDs with unguessable tokens, source format signature checks and strict MIME/content validation, signed upload permissions (size/type/time bound), and upload completion verification.
3. Resumable uploads with retry, cancellation, progress indicator and streaming/safe temporary working storage.
4. Dedicated worker with resource caps for CPU, memory, storage, file duration, dimensions, archive bombs and runtime; isolate LibreOffice/FFmpeg subprocesses. Scrub metadata where appropriate; document realistic limitations.
5. Malware scanning or sandboxing and antivirus policy, output validation, safe download headers, short retention, and automatic cleanup after success or failure.
6. End-to-end tests for at least one legitimate **500 MB** file, simultaneous uploads, reconnect/retry, transcoding, output download, forced timeout, malformed file, and cleanup.
7. Update API capabilities to 500 MB **only after** steps 1–6 are verified. Avoid a misleading "500 MB" badge until then.

## Domain options
- Free temporary Firebase-hosted URL: `<chosen-project-id>.web.app`, allocated when a Firebase project is created.
- Custom student domain: must be registered by the owner after GitHub Student Developer Pack eligibility and renewal terms are checked.
- If a domain is bought/claimed, connect it to Firebase Hosting in the Firebase console, add the provided DNS records in the registrar, and wait for certificate/ownership verification.
- Update canonical tags, sitemap, robots.txt and Google Search Console only after the final domain is working. Redirect the old domain with a permanent redirect when appropriate; avoid splitting SEO ranking signals across multiple active canonical origins.

## First deployment decision
Keep the current working Render app online until the new API, storage and compute are deployed and pass file-conversion smoke tests. Then deploy the static frontend to Firebase Hosting, verify uploads, conversion and downloads through the new hostname, and switch the canonical origin.

## UX additions on feature branch
- Developer: **Mr. Uday Payghon**, with linked public LinkedIn contact.
- Image output sizing: visible, optional KB/MB target card; preserved aspect ratio and crop tools.
- Best-effort near-target selector (still a size ceiling; byte-exact output size is not guaranteed).
- Clean file downloads: no watermark intentionally inserted by the converter. Input metadata or content is not guaranteed to be stripped.
- Non-blocking `Your conversion is complete.` success notification with direct download.
- Capacity notice in Video workspace truthfully displays the current server limit.
