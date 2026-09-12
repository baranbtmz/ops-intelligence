# Production recovery — 2026-09-12

The login outage was caused by a revoked Supabase server key in Railway. The existing server credential was restored; invalid credentials now return 401 instead of an unhandled 500. Database API failures return a safe 503, and the browser retains its session during temporary service failures.

Shopify now requests expiring offline tokens and stores refresh tokens only in the backend users.stores field. Legacy tokens are cycled before use; renewal is serialized for the current single-replica deployment. Before scaling replicas, move refresh coordination into a database lock/transaction. The embedded dashboard requires a verified Shopify session before issuing an OPS session. Shop profile email is not proof of OPS account ownership.

The ops-intelligence.myshopify.com token was renewed and its orders API returned 200. The ed915z-qu.myshopify.com token is invalid and requires merchant reconnection with the existing Shopify account. Reconnection, not a saved “connected” label, is the authority for restored access.

OpenAI analysis and Ask OPS use Responses with gpt-6-astra by default. Optional server environment overrides: OPENAI_ANALYSIS_MODEL, OPENAI_ASK_MODEL, OPENAI_REASONING_EFFORT (default low), OPENAI_TIMEOUT_SECONDS (default 75). Existing OPENAI_API_KEY is reused. Requests use store=false and bounded retries. A real Astra JSON smoke request succeeded.

Inventory item costs are read from Shopify. Missing cost stays unknown and must not be presented as zero-cost profit. The home screen provides direct connections, analysis, ledger, and analyst entry points. Ledger/team functionality remains the existing implementation; this recovery does not introduce shared accounting storage.

## Validation

Run `.venv/bin/python -m pytest -q test_recovery.py` after installing requirements_api.txt and pytest. Fourteen targeted tests cover login, safe database errors/CORS, Shopify session isolation, renewable token persistence, Astra output handling and missing-cost semantics. Frontend inline JavaScript passes node --check; desktop and 390px mobile views were checked in the browser.

## Deployment

GitHub: baranbtmz/ops-intelligence. Railway: ops-intelligence production. Netlify: opswebsitedot (opsintelligence.org). Publish only netlify-public via the existing netlify.toml build command; never publish the repository root or environment files. No schema or RLS changes were made. Users table RLS remains enabled.

After deployment check /health, invalid /auth/login returns 401 with CORS, and unauthenticated /shopify/app shows only the App Bridge bootstrap. A real merchant login and the remaining Shopify consent must be verified using the merchant's existing authenticated session; do not synthesize a customer login token for a smoke test.

The bilingual guide is served at /guide.html and linked from the homepage and dashboard. It includes an address-format checker, a five-step checklist, plan distinctions and troubleshooting. Short entrance animations honor prefers-reduced-motion.
