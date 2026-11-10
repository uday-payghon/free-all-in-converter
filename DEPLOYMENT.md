# Deployment runbook — Free All-in Converter

## Actual status (10 November 2026)

Deployed and verified at **https://free-all-in-converter.onrender.com**. Source: https://github.com/uday-payghon/free-all-in-converter. Render Free service `srv-dbpc560m7kps73agkah0` runs in Uday's workspace, Singapore. Initial deploy `dep-dbpc56gm7kps73agkbsg` became live on 10 November 2026. All six public HTTPS conversion smoke tests passed, including readable Office/PDF/media downloads and error handling.

No custom domain has been registered or configured, and no Student Developer Pack benefit has been redeemed. Student verification and registrar access remain unverified. Render Free hosting and its included HTTPS hostname do not require the Student Pack. Browser access for redemption is disabled in this session's Work settings.

The service was created directly through Render MCP. Its current health check uses Render's default TCP check; `/health` is independently verified by HTTP. The supplied Blueprint specifies `/health` for future Blueprint deployments. The MCP creation tool does not expose HTTP health-check configuration.

## Reproducible release checks

```sh
docker build --target test -t converter:test .
docker run --rm --memory=512m --cpus=1 --pids-limit=128 converter:test
docker build --target production -t converter:production .
docker run -d --name converter --memory=512m --cpus=1 --pids-limit=128 \
  --security-opt no-new-privileges --cap-drop ALL --read-only \
  --tmpfs /tmp:rw,nosuid,size=256m --tmpfs /home/appuser:rw,nosuid,size=32m \
  -p 127.0.0.1:10000:10000 -e MAX_UPLOAD_MB=40 -e RATE_LIMIT_PER_MINUTE=0 converter:production
docker run --rm converter:test python scripts/smoke.py http://host.docker.internal:10000
```

On Linux use `--network host` and `http://127.0.0.1:10000` for the smoke-test container. Disable rate limiting only during repeated local tests. Browser instructions are in README; CI runs backend, real HTTP, browser and accessibility checks. The initial GitHub Actions run itself must be verified after publishing; local tests do not prove that a remote workflow has run.

## Publish and deploy when authorized/connected

1. Review the staged project and `docs/QA.md`. Confirm creation of the proposed **new public** repository `uday-payghon/free-all-in-converter`. If that name exists, inspect it and choose another new name; never overwrite another repository. Keep `.env`, uploads, test outputs and dependencies out of Git.
2. Create and push the dedicated repository. The connected GitHub plugin has no repository-creation action; the authenticated GitHub CLI can perform creation after authorization.
3. Connect Render and select **New > Blueprint** for that repository. Review `render.yaml` and choose the Free plan. The final Docker stage is production; no test dependencies or frontend build service are required. Do not add a database, login or payment.
4. Defaults in the Blueprint: 40 MB uploads, 16 MP images, 80 PDF pages, one conversion, three active requests, five-second queue wait, 240-second deadline, 12 attempts/minute/peer. The worker has a 1 GiB virtual-address ceiling; that is separate from the container's real RAM limit. Heavy files may still exceed Free compute capacity.
5. Observe the complete build/deploy and `/health`. Use the actual assigned `https://…onrender.com` hostname, not a guessed address.
6. Run the live gate (requires test image from step 1):

   ```sh
   docker run --rm converter:test python scripts/smoke.py https://ACTUAL-SERVICE.onrender.com --public
   ```

   This checks six real conversions, opens/decodes their downloads, validates filenames and verifies a malformed-file error. Save the actual output, URL and time in `docs/QA.md`. Then run the browser suite with `BASE_URL` set to that URL, respecting the public rate limit.
7. Confirm `/health`, homepage, all categories, crop, size failure, downloads and HTTPS from outside the host. Only then record a successful deployment.
8. Configure trusted ingress CIDRs only after verifying Render's proxy topology and header rewriting. The app ignores arbitrary forwarded headers by default, so clients behind a shared proxy share its quota. For real public traffic add external throttling and complete the outstanding items in [SECURITY.md](docs/SECURITY.md).

[Render Free documentation](https://render.com/docs/free) says services sleep after 15 idle minutes and may take about a minute to wake. Free has ephemeral storage, bandwidth/build/compute quotas and is not recommended for production applications. [Render web-service documentation](https://render.com/docs/web-services) describes the assigned hostname and runtime. The local Docker flags above are not automatically enforced by a Render Blueprint.

## GitHub Student Developer Pack domain

The [official Pack page](https://education.github.com/pack), checked 10 November 2026, lists:

| Provider | Listed offer |
| --- | --- |
| Namecheap | One year registration of an eligible `.me` domain |
| Name.com | An eligible free domain from selected extensions, including `.live`, `.studio`, `.software`, `.app`, `.dev` |
| .TECH | One standard `.tech` domain free for one year |

Redemption depends on verified student eligibility, an unused offer, registrar terms and domain availability. Check the checkout total, premium-name exclusions, renewal price, auto-renewal and expiry before accepting. A first-year offer does not make renewals free. No domain search, registration, ownership or student eligibility has been verified for this project.

After selecting a domain you own and verifying the Render service:

1. Add the domain in the service's **Settings > Custom Domains**.
2. Follow the precise DNS records Render displays. Typically use `CNAME www -> actual-service.onrender.com`; use a supported `ALIAS`/`ANAME` for the apex or Render's displayed A record. Preserve unrelated mail/TXT records. Remove conflicting web/AAAA records only for the hostname being configured, after inspecting existing use.
3. Verify DNS, then Render domain verification and automatic TLS. Render supplies managed TLS; a separate student SSL certificate is unnecessary here.
4. Check the custom HTTPS homepage and repeat `scripts/smoke.py https://YOUR-DOMAIN --public` and browser downloads. Record the final canonical domain and redirects.

Official instructions: [Custom domains](https://render.com/docs/custom-domains), [DNS configuration](https://render.com/docs/configure-other-dns), [managed TLS](https://render.com/docs/tls).

## Firebase alternative

The frontend can be hosted separately, but Firebase Spark Hosting cannot run Python, FFmpeg, Ghostscript or LibreOffice. A split deployment requires a separate compute service, explicit API origin and restricted CORS. It is not implemented or needed for this single-service release.
