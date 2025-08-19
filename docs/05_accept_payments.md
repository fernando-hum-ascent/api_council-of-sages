## Accept payments with Stripe (credit-based top-ups)

This plan integrates Stripe payments to credit user balances in integer tenths-of-cents, aligned with the token/cost plan in `docs/04_add_token_count.md` while adapting to the current storage unit:

- **Source of truth**: `models/user.py` keeps `balance_tenths_of_cents` authoritative.
- **LLM costs**: Still tracked via `UsageEvent` and decremented by the `BillingLLMProxy` after calls (convert to tenths-of-cents at the decrement boundary if calculators yield cents).
- **Top-ups**: Handled by Stripe, crediting `User.balance_tenths_of_cents` only via a verified webhook with strict idempotency. Stripe amounts are in cents; convert to tenths-of-cents by multiplying by 10.

---

## Goals

- **Simple, secure purchase flow**: Create a PaymentIntent server-side, confirm on the client with Stripe.js, and finalize via webhook.
- **Server-validated variable amounts**: The user selects how much to recharge; the server enforces min/max USD constraints. Never trust client-provided `user_id`.
- **Idempotency**: Ensure a Stripe event or intent is processed at most once.
- **Full alignment with billing**: Balance changes from payments are additive and independent from LLM usage deductions.

---

## Backend endpoints (FastAPI)

Implement in `resources/payments.py` and `resources/webhooks.py` (keeps plural file naming per repo rules). If you prefer the suggested paths below unchanged, you can mount the webhook route under `resources/payments.py` too.

### 1) POST `/payments/create-payment-intent` (auth required)

- **Body** (variable amount top-up):
  - `{ "amount_usd": number }`
  - Server validates against constraints: `min_topup_usd` and `max_topup_usd`.
- **Behavior**:
  - Resolve `user_id` from auth context (see Auth section below), not from request body.
  - Validate the requested USD amount against min/max, then compute:
    - `amount_cents` for Stripe (USD → cents)
    - `requested_amount_tenths_of_cents = amount_cents * 10` for auditing
  - Create PaymentIntent:
    - `amount=amount_cents`, `currency='usd'`
    - `automatic_payment_methods={'enabled': True}`
    - `metadata={'user_id': <from auth>, 'requested_amount_tenths_of_cents': <requested_amount_tenths_of_cents>}`
- **Response**:
  - `{ client_secret, intent_id, amount_cents, currency , status }`

### 2) POST `/webhooks/stripe` (no auth; signature verified)

- **Verification**: Use `STRIPE_WEBHOOK_SECRET` to verify the `Stripe-Signature` header.
- **On `payment_intent.succeeded`**:
  - Read `intent.id`, `intent.amount_received`, and `intent.metadata.user_id`.
  - Upsert a `Payment` record (see Data model) with idempotency on `stripe_event_id` and `stripe_intent_id`.
  - Resolve `User` via `user_id` (get-or-create). Atomically increment `User.balance_tenths_of_cents` by `amount_received * 10`.
  - Mark the `Payment` as `succeeded`.
  - Important: Use `intent.amount_received` (not `amount`) and update balance only here (webhook), never in the intent-creation endpoint or client callbacks.
- **On `payment_intent.payment_failed` / `payment_intent.canceled`**:
  - Persist `Payment` with `failed` status; do not mutate balance.
- **Return**: 200 quickly on success; 4xx on signature errors; 2xx even if duplicate (already processed) to avoid retries storm.

---

## Data model (MongoEngine)

Add a new document `models/payment.py` for auditability and idempotency. Balance remains solely in `models/user.py`.

- **Fields**:
  - `id`: string primary key (e.g., `uuid_field("PAY_")`)
  - `stripe_intent_id`: string (unique)
  - `stripe_event_id`: string (unique; for webhook idempotency)
  - `user_internal_id`: string (references `User.id`)
  - `user_id`: string (from auth provider, as in `User.user_id`) for easier queries
  - `amount_cents`: int (Stripe amount)
  - `currency`: string, default `"usd"`
  - `status`: enum-like string: `"requires_payment_method" | "processing" | "succeeded" | "failed" | "canceled"`
  - `requested_amount_tenths_of_cents`: optional int (from metadata), for audit
  - `credited_tenths_of_cents`: optional int (what was finally credited = `amount_received * 10`)
  - `created_at`, `updated_at`: datetimes
- **Indexes**:
  - Unique on `stripe_intent_id`
  - Unique on `stripe_event_id`
  - Secondary on `user_internal_id`, `created_at`

---

## Auth & context

- Use the existing auth dependency to set a ContextVar (see token plan `lib/auth/context.py`).
- Derive `user_id` on the server in all payment operations. Do not accept `user_id` from the client.

---

## Server-side amount validation (custom recharge)

Enforce guardrails for user-selected amounts (validate in USD; tenths-of-cents remain the storage/audit unit):

- `min_topup_usd` (e.g., 1) and `max_topup_usd` (e.g., 500)
- Always convert to Stripe cents for intent creation and validate currency is `usd`

Amount conversion and rounding guidelines:

- Parse `amount_usd` using Decimal, not float, to avoid precision errors.
- Validate `amount_usd` against `min_topup_usd <= amount_usd <= max_topup_usd`.
- Compute `amount_cents = int((Decimal(amount_usd) * Decimal("100")).quantize(Decimal("1")))`.
- Derive `tenths = amount_cents * 10` for auditing and consistency with balance storage.

---

## Configuration

- **Env vars** (add to `config.py` and `.env.example`):
  - `STRIPE_SECRET_KEY`
  - `STRIPE_WEBHOOK_SECRET`
  - `PAYMENTS_MIN_TOPUP_USD` (e.g., 1)
  - `PAYMENTS_MAX_TOPUP_USD` (e.g., 500)
- **Dependencies** (`pyproject.toml`):
  - `stripe` (official Stripe Python SDK)

---

## Interaction with billing and token usage

- The `BillingLLMProxy` continues to perform pre-request balance checks and post-response decrements based on token usage and prices.
- Payments only ever increase `User.balance_tenths_of_cents` via the webhook after a confirmed, verified event.
- Current cost calculators already return `cost_tenths_of_cents`; use that unit consistently for decrements.
- The `GET /users/me/balance` endpoint (from the token/cost plan) remains the canonical way for the frontend to fetch the current balance. Clients can refresh balance after checkout success.

---

## Security considerations

- **Do not trust client-provided user identifiers**. Always derive `user_id` from auth context.
- **Validate client-provided amounts** strictly against server-side constraints (min/max), and reject invalid requests.
- **Verify webhook signatures** using `STRIPE_WEBHOOK_SECRET`. Reject on verification failure.
- **Idempotency**: Ensure both `stripe_event_id` and `stripe_intent_id` uniqueness to avoid double credits.
- **Logging**: Record failed events for observability.

---

## When should the balance be updated?

- Update `User.balance_tenths_of_cents` **only** in the Stripe webhook after signature verification and **only** on `payment_intent.succeeded`.
- Do **not** update balance in:
  - `POST /payments/create-payment-intent` (creation endpoint)
  - Client-side success callbacks (Stripe.js)
  - Events like `payment_intent.created`, `requires_payment_method`, `requires_action`, `processing`, or `canceled`
- For manual capture flows (`capture_method=manual`), credit the balance only after the intent transitions to `succeeded` (funds captured). Never on `requires_capture`.
- Always credit using `amount_received * 10` (convert cents → tenths-of-cents). Never use any client-provided amount for crediting.
- Ensure idempotency by recording both `stripe_event_id` and `stripe_intent_id`; skip credit if either was already processed.

Implementation note with current model methods:

- `User.async_decrease_balance(amount_tenths_of_cents)` is documented as "positive = deduction" and uses a decrement update.
- For credits, do not call it with positive values. Prefer adding a `User.async_add_balance(credited_tenths: int)` helper to avoid sign errors.

---

## Suggested responses

### POST `/payments/create-payment-intent` response

```json
{
  "client_secret": "pi_123_secret_abc",
  "intent_id": "pi_123",
  "amount_cents": 1000,
  "currency": "usd",
  "status": "requires_payment_method"
}
```

### POST `/webhooks/stripe` behavior

- Returns 200 on valid, processed or already-processed events.
- Returns 400/401 on signature verification errors.

---

## Implementation checklist

- **models**:
  - `models/payment.py` with fields and unique indexes (`stripe_event_id`, `stripe_intent_id`).
- **lib/auth**:
  - Ensure `current_user_id_var` ContextVar is set by FastAPI auth dependency to derive user context in payments.
- **lib/billing**:
  - Add `amount_validation.py` (optional) encapsulating min/max USD validation for clarity and reuse.
- **resources**:
  - `POST /payments/create-payment-intent` (auth): create PaymentIntent from a validated `amount_usd`, computed into cents for Stripe and tenths-of-cents for audit.
  - `POST /webhooks/stripe` (no auth): verify signature, upsert `Payment`, credit `User.balance_tenths_of_cents` with `amount_received * 10` idempotently.
- **config**:
  - Add `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and USD min/max constraints; load and validate in `config.py`.
- **deps**:
  - Add `stripe` to `pyproject.toml` and install.
  - Ensure `decimal`-based conversion for `amount_usd` in validation logic.

---

## Minimal code sketch (for reference only)

```python
# create intent (inside resources/payments.py)
import stripe

stripe.api_key = settings.stripe_secret_key

@router.post("/payments/create-payment-intent")
async def create_payment_intent(req: CreateIntentRequest, user_id: str = Depends(get_current_user_id)):
    amount_cents = validate_amount_usd_and_to_cents(req)  # enforce min/max USD on server
    requested_tenths = amount_cents * 10  # audit in tenths-of-cents
    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="usd",
        automatic_payment_methods={"enabled": True},
        metadata={"user_id": user_id, "requested_amount_tenths_of_cents": requested_tenths},
    )
    return {
        "client_secret": intent.client_secret,
        "intent_id": intent.id,
        "amount_cents": amount_cents,
        "currency": "usd",
        "status": intent.status,
    }
```

```python
# webhook (inside resources/webhooks.py)
import stripe

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("Stripe-Signature")
    event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        upsert_payment_and_credit_user(intent=intent, stripe_event_id=event["id"])  # idempotent
    elif event["type"] in {"payment_intent.payment_failed", "payment_intent.canceled"}:
        record_failed_payment(event)
    return Response(status_code=200)
```

These sketches are illustrative; follow the repository's structure and validators per `general_cursor_rules`.

---

## Frontend integration (high level)

- Call `POST /payments/create-payment-intent` after the user enters the recharge amount.
- Confirm the PaymentIntent on the client using Stripe.js.
- After the success screen, poll `GET /users/me/balance` to reflect the new credits (webhook updates the balance asynchronously).

---

## Testing

- Unit tests:
  - Intent creation validates `amount_usd` against min/max and derives `user_id` from auth.
  - Webhook signature verification and idempotent crediting.
  - Balance increment and `Payment` persistence.
- Integration tests:
  - Simulate Stripe events using signed payloads or the Stripe CLI in test mode.


### Webhook local development

Use Stripe CLI to forward webhooks to your local backend:


### Testing with Stripe CLI (step‑by‑step)

This section shows how to fully test the top‑up flow end‑to‑end using Stripe CLI in test mode.

1) Install and authenticate CLI

```bash
# macOS (Homebrew)
brew install stripe/stripe-cli/stripe

# Login (opens browser)
stripe login
```


2) Forward webhooks to your backend

```bash
# Basic listener (all test events)
stripe listen --forward-to localhost:8080/stripe/webhook

# Optionally, limit to relevant events for this flow
stripe listen --events payment_intent.succeeded,payment_intent.payment_failed \
  --forward-to localhost:8080/stripe/webhook
```

- The command prints a signing secret like `whsec_...`. Set it so your backend can verify signatures:

```bash
export STRIPE_WEBHOOK_SECRET=whsec_...
```

3) Start your backend locally

- Ensure the webhook endpoint exists at `POST /stripe/webhook` and does NOT require auth
- Export your test secret key and webhook secret in your backend environment

```bash
export STRIPE_SECRET_KEY=sk_test_...
# start your backend on port 8080
```

4) Run the frontend and create a test payment

- Ensure `.env` contains `VITE_STRIPE_PUBLISHABLE_KEY=pk_test_...`
- Start the frontend, open the Top‑up dialog, pick an amount, and pay with a test card:
  - 4242 4242 4242 4242 with any future expiry and any CVC
  - For 3DS testing: 4000 0027 6000 3184

What you should see:

- The browser completes confirmation (`stripe.confirmPayment`)
- Stripe emits a webhook event; the CLI forwards it to `localhost:8080/stripe/webhook`
- Your backend handles `payment_intent.succeeded` and credits the user
- The frontend balance refresh reflects the new amount within a few seconds

5) Verify and inspect events

```bash
# Tail webhook activity
stripe logs tail

# List recent events
stripe events list --limit 10

# Inspect a single event payload
stripe events retrieve evt_123
```

6) Simulate events without the UI (for endpoint-only testing)

```bash
# Triggers a full PaymentIntent flow and sends webhooks
stripe trigger payment_intent.succeeded
stripe trigger payment_intent.payment_failed
```

Notes:

- `stripe trigger` creates test objects on Stripe and may not include your `metadata.user_id`. Use this to validate your webhook signature handling and error paths, not for balance mutation logic that relies on metadata. For end‑to‑end balance testing, use the actual frontend flow (so the server creates the intent with the correct metadata).

7) Common issues

- Invalid signature: ensure your backend uses the exact `STRIPE_WEBHOOK_SECRET` printed by `stripe listen`
- 401/403 at `/stripe/webhook`: remove auth; verification happens via signature
- 404: confirm the path matches `--forward-to`
- No balance update: check backend logs; verify `event.type` is `payment_intent.succeeded` and `metadata.user_id` is present on the intent
- Using live keys by mistake: ensure both frontend and backend use test keys in dev

8) Testing remote dev/staging

```bash
# Forward webhooks to a remote URL instead of localhost
stripe listen --forward-to https://your-dev-host/stripe/webhook
```

9) Clean up

- Stop the listener with Ctrl+C
- Unset local env vars if needed: `unset STRIPE_WEBHOOK_SECRET STRIPE_SECRET_KEY`

---
