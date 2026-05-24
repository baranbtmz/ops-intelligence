# OPS Intelligence Shopify Launch Checklist

## Current app config

- App name: OPS Intelligence
- App handle: ops-intelligence
- App URL: https://ops-intelligence-production.up.railway.app/shopify/app
- OAuth callback: https://ops-intelligence-production.up.railway.app/shopify/callback
- Uninstall webhook: https://ops-intelligence-production.up.railway.app/shopify/webhooks/app-uninstalled
- Privacy webhook: https://ops-intelligence-production.up.railway.app/shopify/webhooks/privacy
- API version: 2026-01
- Scopes: read_orders, read_products, read_inventory, read_fulfillments, read_locations

## Shopify Dev Dashboard

- Confirm the Dev Dashboard app client ID matches `shopify.app.toml`.
- Select Public distribution for App Store sale.
- Keep embedded app enabled.
- Add the App URL and redirect URL exactly as listed above.
- Add the webhook URLs exactly as listed above.
- Configure app pricing in Shopify if using Shopify App Pricing.
- Create a development store and install OPS there before review.

## Railway environment variables

- `SHOPIFY_API_KEY`
- `SHOPIFY_API_SECRET`
- `SHOPIFY_SCOPES`
- `SHOPIFY_API_VERSION=2026-01`
- `SHOPIFY_BILLING_MODE=shopify_app_pricing`
- `SHOPIFY_APP_HANDLE=ops-intelligence-aurellia`
- `SHOPIFY_APP_PRICING_HANDLE=ops-intelligence-aurellia`
- `BACKEND_PUBLIC_URL=https://ops-intelligence-production.up.railway.app`
- `FRONTEND_PUBLIC_URL=https://opsintelligence.org`
- `JWT_SECRET` with a strong production-only random value
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `OPENAI_API_KEY`
- `RESEND_API_KEY` if email delivery is enabled

## Development store test

- Install from the Shopify app install URL.
- Approve OAuth scopes.
- Confirm `/shopify/callback` redirects back to `/shopify/app`.
- Confirm the embedded Shopify app renders inside Shopify admin.
- Click Reinstall permissions and verify OAuth opens again.
- Click Analyze Shopify data and verify live store metrics return.
- Click paid plan buttons and verify Shopify plan selection opens.
- Uninstall the app and verify the store is marked uninstalled.
- Trigger privacy webhooks or test with signed webhook requests before App Store submission.

## App Store submission notes

- Explain `read_orders`, `read_products`, `read_inventory`, `read_fulfillments`, and `read_locations` as required for operational analysis, inventory health, fulfillment delay detection, and store-level KPI reporting.
- `read_all_orders` is intentionally not requested in the first public submission to avoid unnecessary historical order access. Add it only if OPS later needs historical analysis beyond Shopify's standard order access window and after Shopify approves the protected scope.
- State that OPS stores Shopify access tokens, store connection metadata, and aggregate analysis output, but does not persist Shopify customer profiles.
- Provide reviewer instructions with a development store that has orders, products, inventory, and fulfillment data.
- Include privacy policy, terms, support email, and support URL in the listing.

## Review risk items to close

- Confirm the production app is owned by the Shopify Partner account, not a shop-owned custom app.
- Confirm Shopify App Pricing is configured before relying on the pricing URL.
- Confirm privacy webhook behavior matches the published privacy policy.
- Confirm the default JWT secret is overridden in production.
- Confirm all screenshots show the embedded Shopify app and full OPS dashboard.
