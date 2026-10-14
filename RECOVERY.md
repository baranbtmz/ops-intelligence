# Production recovery — 2026-09-12

The login outage was caused by a revoked Supabase server key in Railway. The existing server credential was restored; invalid credentials now return 401 instead of an unhandled 500. Database API failures return a safe 503, and the browser retains its session during temporary service failures.

Shopify now requests expiring offline tokens and stores refresh tokens only in the backend users.stores field. Legacy tokens are cycled before use; renewal is serialized for the current single-replica deployment. Before scaling replicas, move refresh coordination into a database lock/transaction. The embedded dashboard requires a verified Shopify session before issuing an OPS session. Shop profile email is not proof of OPS account ownership.

The ops-intelligence.myshopify.com token was renewed and its orders API returned 200. The separate retail store is outside this development task and is not a prerequisite for app testing. Actual API access, not a saved “connected” label, is the authority for restored access.

OpenAI analysis and Ask OPS use Responses with gpt-6-astra by default. Optional server environment overrides: OPENAI_ANALYSIS_MODEL, OPENAI_ASK_MODEL, OPENAI_REASONING_EFFORT (default low), OPENAI_TIMEOUT_SECONDS (default 75). Existing OPENAI_API_KEY is reused. Requests use store=false and bounded retries. A real Astra JSON smoke request succeeded.

Inventory item costs are read from Shopify. Missing cost stays unknown and must not be presented as zero-cost profit. The home screen provides direct connections, analysis, ledger, and analyst entry points. Ledger/team functionality remains the existing implementation; this recovery does not introduce shared accounting storage.

## Validation

Run `.venv/bin/python -m pytest -q test_recovery.py` after installing requirements_api.txt and pytest. Fifteen targeted tests cover login, safe database errors/CORS, Shopify session isolation, renewable token persistence, Astra output handling and missing-cost semantics. Frontend inline JavaScript passes node --check; desktop and 390px mobile views were checked in the browser.

## Deployment

GitHub: baranbtmz/ops-intelligence. Railway: ops-intelligence production. Netlify: opswebsitedot (opsintelligence.org). Publish only netlify-public via the existing netlify.toml build command; never publish the repository root or environment files. No schema or RLS changes were made. Users table RLS remains enabled.

After deployment check /health, invalid /auth/login returns 401 with CORS, and unauthenticated /shopify/app shows only the App Bridge bootstrap. A real merchant login and the remaining Shopify consent must be verified using the merchant's existing authenticated session; do not synthesize a customer login token for a smoke test.

The bilingual guide is served at /guide.html and linked from the homepage and dashboard. It includes an address-format checker, a five-step checklist, plan distinctions and troubleshooting. Short entrance animations honor prefers-reduced-motion.

## Shopify public-launch status

The authenticated Partners dashboard reports App Store review as Paused. Automated common-error checks were rerun and passed. Do not declare public merchant installation available or attest that all review requirements are met until the reviewer’s requirement issues have been resolved. The public guide and connection screen disclose that general installation is not open yet.

A full live pipeline read 26 products and 0 orders from the authorized test store. A real GPT-6 Astra analysis using synthetic sample data completed with five findings and an executive summary. Free currently permits one basic analysis per month; its OpenAI report is disabled.

The project uses the authorized ops-intelligence development store. The separate retail store subscription is unrelated; no subscription or purchase was made. Specific reviewer feedback is still needed to resolve the paused review.

## Follow-up — 2026-09-13

Safari exposed an additional login failure: a cached upstream connection raised httpx.RemoteProtocolError (server disconnected). The Supabase transport now uses HTTP/1.1 without idle keepalive sockets and retries one interrupted GET/HEAD read, never a write. Exhausted transport failures return safe JSON with CORS and status 503. Login runs in the worker pool so its synchronous database and bcrypt work do not block the event loop. Tests cover the actual transport failure, bounded reads and non-replayed writes.

The installed app opened successfully inside the ops-intelligence development store in Safari. Its verified Open OPS action reached the authenticated web workspace with the correct development store connected.

The public homepage and login now use the green/cream theme; these were previously still using the original design. Both languages, mobile layout, keyboard-operable login tabs, source labels and reduced-motion behavior are included. Decorative charts are explicitly illustrative. The homepage links to the guide and accurately discloses the current Shopify review limit.

After the transport fix deployed, resubmitting the already-filled email/password form in Safari successfully opened the existing user dashboard. No password was extracted, reset or changed. The development-store Shopify handoff was also verified independently.

## Follow-up — 2026-10-14

The production Supabase project was INACTIVE while Railway remained healthy. Restore was requested via the Supabase management connector. This incident is distinct from the earlier revoked key and idle connection issues. The user requested their original gold/black branding and animated homepage; index.html was restored from the existing source and the auth/guide/workspace accents returned to that palette without reverting authentication fixes.
