## Token and cost tracking plan

This document describes how we will track tokens and cost per user across the API with minimal duplication and high reusability.

- **Goal**: Ensure every LLM request is billed consistently by model/token usage; enforce available balance prior to running expensive calls; return the updated balance in responses.
- **Scope**: New `User` model, a pricing map, token counting utilities, a reusable billing service with a simple integration pattern for endpoints, and response augmentation.

---

### 1) User model in MongoDB (mongoengine_plus)

- **File**: `models/user.py`
- **Fields**:
  - `id`: str (generated with `uuid_field("USR_")`)
  - `user_id`: str (external id from auth provider; unique index)
  - `balance_cents`: int (store currency in integer cents for atomicity and correctness)
  - `created_at`: datetime
  - `updated_at`: datetime
- **Defaults**:
  - On creation, set `balance_cents = 100` (1 USD)
- **Indexes**:
  - Unique on `user_id`
- **Notes**:
  - Use integer cents to avoid floating point issues and simplify atomic `$inc` updates.
- **methods**
  - Create a get_or_create async method
  - Add an instance helper `as_balance()` returning the `Balance` Pydantic model from `types.py` (or `as_balance_dict()` via `Balance.model_dump()`), with fields `{"balance_cents", "balance_usd", "updated_at"}`

Example (conceptual):
```python
class User(BaseModel, AsyncDocument):
    id = StringField(primary_key=True, default=uuid_field("USR_"))
    user_id = StringField(required=True, unique=True)
    balance_cents = IntField(required=True, default=100)  # 1 USD
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
```

#### 1.1) usage_event in mongo

- **File**: `models/usage_event.py`
- **Purpose**: Auditing and analytics.
- **Fields**: `user_internal_id`, `request_id`, `model_name`, `input_tokens`, `output_tokens`, `cost_cents`, `provider_request_id`, `status`, `created_at`.
- **Indexes**:
  - Unique compound index on `(user_internal_id, request_id)` for idempotency
  - Secondary indexes on `user_internal_id` and `created_at`


---

### 2) Pricing map: per-model, input/output prices

- **File**: `lib/billing/costs.py`
- **Format**: Use `Decimal` for prices or store integer microcents per 1K tokens. Convert to integer cents once at the boundary using ROUND_HALF_UP.
- **Structure**:
```python
from decimal import Decimal

MODEL_PRICING = {
    # Example values. Replace with real ones from providers.
    "gpt-4o-mini": {
        "input_usd_per_1k": Decimal("0.1500"),
        "output_usd_per_1k": Decimal("0.6000"),
        "tokenizer": "openai",
    },
    "gpt-4o": {
        "input_usd_per_1k": Decimal("5.0000"),
        "output_usd_per_1k": Decimal("15.0000"),
        "tokenizer": "openai",
    },
    "claude-3-5-haiku-20241022": {
        "input_usd_per_1k": Decimal("0.2500"),
        "output_usd_per_1k": Decimal("1.2500"),
        "tokenizer": "anthropic",
    },
}
```
---

### 3) Reusable billing utilities

- **Files**:
  - `lib/billing/token_count.py`: vendor-aware token counting
  - `lib/billing/calculator.py`: cost computation
  - `lib/billing/service.py`: high-level orchestration used by the proxy

- **Token counting** (`lib/billing/token_count.py`):
  - `count_input_tokens(model_name, prompt_or_messages) -> int`
  - `count_output_tokens(model_name, response_text_or_content, response_metadata) -> int`
  - Prefer vendor tokenizers (e.g., `tiktoken` for OpenAI; Anthropic tokenizer if available).
  - Fallback: heuristic estimator when metadata is missing.

- **Cost calculator** (`lib/billing/calculator.py`):
```python
from decimal import Decimal, ROUND_HALF_UP

def calculate_cost_cents(model_name: str, input_tokens: int, output_tokens: int) -> int:
    prices = get_model_prices(model_name)
    input_cost_usd = (Decimal(input_tokens) / Decimal(1000)) * prices.input_usd_per_1k
    output_cost_usd = (Decimal(output_tokens) / Decimal(1000)) * prices.output_usd_per_1k
    total_usd = input_cost_usd + output_cost_usd
    return int((total_usd * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
```
  - We store costs as integer cents and convert once at the boundary with ROUND_HALF_UP.

- **Billing service** (`lib/billing/service.py`):
  - Internals used by the proxy to count tokens, compute cost in cents, and perform atomic updates/logging.


### 5)  Centralized proxy llm cost manager

Adopt a single, centralized wrapper so call sites remain unchanged. The proxy will infer the model from the underlying client, so you do not need to pass the model name twice.

- **File**: `lib/billing/billing_llm_proxy.py`
- **Class**: `BillingLLMProxy`
- **Responsibilities**:
  1. Resolve current user via a `contextvars.ContextVar` set by FastAPI auth dependency.
  2. Execute the underlying client call (`invoke`, `ainvoke`, and optionally `stream`/`astream`).
  3. Extract `response_metadata` to compute tokens and final cost.
  4. Atomically decrement the user's balance and log a `UsageEvent`.
  5. Expose billing info through a `BillingContext` contextvar so the API layer can attach it to the HTTP response without changing orchestrator signatures.
  6. Ensure idempotency by using a `request_id` (from a ContextVar set by the HTTP layer, or generated by the proxy) and deduplicating via the unique `(user_internal_id, request_id)` index in `UsageEvent`.

- **Model inference (no duplication)**:
  - The proxy introspects the base client to determine the model name. Common patterns:
    - LangChain OpenAI: `getattr(base_llm, "model", None)`
    - LangChain Anthropic: `getattr(base_llm, "model", None)`
    - OpenAI SDK client wrappers: read from configuration or request kwargs captured during call.
  - If the model cannot be inferred, the proxy will raise a clear error instructing to set a model on the base client. No explicit `model_name` parameter is required by default.

*** Pre-request balance check

- **Where**: Inside the `BillingLLMProxy` (transparent to endpoints).
- **Behavior**:
  - Resolve `User` by `user_id` from auth context using get_or_create (create with default balance if new user).
  - If `balance_cents <= -10`, return 402 Payment Required (or 403 with domain error) before executing the LLM call.
- **Rationale**: Prevents unnecessary spending when the user is clearly out of balance. Deduction is performed post-response inside the proxy to avoid partial updates and duplicated code at call sites.

#### 5.1 Changes in constructor

- **Construction (one-time)**:
```python
from lib.billing.billing_llm_proxy import BillingLLMProxy
from langchain_openai import ChatOpenAI  # example; use your provider

class Moderator:
    def __init__(self, ...) -> None:
        raw_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.distribution_llm = BillingLLMProxy(base_llm=raw_llm)
```

#### 5.2 Refactor LLMs inside functions to be constructed first

- **Important note about function-scoped LLMs**:
  - If any LLMs are constructed inside functions (e.g., `council_of_sages/orchestrator/tools/philosophical_sage.py`), refactor to construct them once and inject the wrapped instance, or wrap the constructed client before use. Otherwise, the "no call-site changes" guarantee does not hold for those sites.

Below are concrete refactor patterns.

##### 5.2.1 Function-scoped construction → module-level singleton (simple modules/tools)

BEFORE (bad): creates a new client on every call, bypassing the billing proxy.
```python
# council_of_sages/orchestrator/tools/philosophical_sage.py
from langchain_openai import ChatOpenAI

async def philosophical_sage(prompt: str) -> str:
    # Constructing the LLM inside the function (anti-pattern for billing)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return await llm.ainvoke(prompt)
```

AFTER (good): construct once at import time, wrap with the billing proxy, and reuse.
```python
# council_of_sages/orchestrator/tools/philosophical_sage.py
from langchain_openai import ChatOpenAI
from lib.billing.billing_llm_proxy import BillingLLMProxy

# Construct raw LLM once and wrap with the billing proxy
_philosophical_llm = BillingLLMProxy(
    base_llm=ChatOpenAI(model="gpt-4o-mini", temperature=0)
)

async def philosophical_sage(prompt: str) -> str:
    # Reuse the pre-wrapped instance; billing is automatic
    return await _philosophical_llm.ainvoke(prompt)
```



Key rules to follow:
- **Construct once, wrap once** with `BillingLLMProxy`, then reuse.
- **Do not** create raw clients inside hot paths (functions called per-request).
- **Inject** the pre-wrapped LLM when possible for better testability.
- **Ensure the base client has its model set** so the proxy can infer pricing/tokenization automatically.

---

### 6) Endpoint integration pattern (proxy-only)

- **Contract**: Endpoints and orchestrators remain unchanged. They call `.invoke`/`.ainvoke` on the wrapped LLM instance.
- **Source of truth for balance**:
  - The `User` document in MongoDB is the single source of truth: `balance_cents` and `updated_at` live there.
  - `UsageEvent` is an audit log only (used for analytics/idempotency), not authoritative for balance.
  - The `Balance` Pydantic model is a read-view derived from `User` (`balance_cents` → `balance_usd`, plus `updated_at`).
- **Under the hood (done by the proxy)**:
  - Resolve user via auth ContextVar and perform a pre-request balance check against `User.balance_cents` (get-or-create if missing)
  - Count input tokens and capture a `request_id`
  - Execute the provider call
  - Extract usage metadata or fall back to tokenizer for output tokens
  - Compute cost in integer cents using Decimal and round once
  - Atomically decrement balance on `User` and persist a `UsageEvent` with deduplication by `(user_internal_id, request_id)`
  - Publish `BillingInfo` into a `BillingContext` so the API layer can append it to responses
- **Failure path (insufficient funds or other pre-check failure)**:
  - The proxy raises a domain error (e.g., `PaymentRequiredError`) before calling the provider.
  - The API layer maps it to HTTP 402 and may include the current `Balance` (proxy can set `BillingContext` with the current user balance on failure as well).

- **How endpoints and orchestrators (e.g., `arun_agent`) interact**:
  - Endpoints/resources remain thin:
    - They construct or receive the wrapped LLM once (during service init) and call orchestrators as usual.
    - After the orchestrator returns, the endpoint reads `BillingContext.get()` to attach `billing.balance` to the HTTP response.
    - On pre-check failure, the endpoint returns 402 and (optionally) includes the `balance` from `BillingContext` so the client can display the current balance.

- **Minimal endpoint example (conceptual)**:
```python
# Inside a FastAPI route handler
result = await orchestrator.run(...)
info = BillingContext.get()  # contains BillingInfo set by the proxy
return {"data": result, "balance": info.balance.model_dump()}
```

- **Fetching balance outside of an LLM call**:
  - Use the dedicated endpoint `GET /users/me/balance`, which loads `User` (get-or-create) and returns `Balance` derived from the authoritative `User` document.

- **Return shape suggestion** (add balance consistently):

Consult balance from the user endpoint
```json
{
  "data": { /* original payload */ , "balance": { "balance_cents": 98, "balance_usd": 0.98, "updated_at": "2025-08-14T12:34:56Z" }},
}
```

- **Glue code**: Not required at endpoint level; the proxy encapsulates pre-check, counting, cost, idempotency, and balance update.

---

### 7) Calculating cost from response metadata

- **Preferred**: Use provider-returned token counts when available:
  - OpenAI: `usage.prompt_tokens`, `usage.completion_tokens`, and `usage.total_tokens`.
  - Anthropic: `usage.input_tokens`, `usage.output_tokens`.
- **Fallback**:
  - If metadata is missing, count tokens from input and generated text with the vendor tokenizer.
- **Final formula**:
  - `total_cost_usd = input_tokens / 1000 * input_usd_per_1k + output_tokens / 1000 * output_usd_per_1k` (use Decimal)
  - Convert to integer cents once with ROUND_HALF_UP

---

### 8) Updating and returning balance

- **When**: After the full flow completes (post-response computation), inside the proxy's finalize step.
- **How**: Single atomic decrement; record a `UsageEvent`. This keeps endpoints clean and avoids partial state.
- **Response**: Always include `balance` in the returned payload. Use the `Balance` Pydantic model for consistency.

---

### 9) Error handling

- **LLM call fails**: Do not deduct. Optionally log a `UsageEvent` with `status = failed` and `cost_cents = 0`.
- **Missing pricing**: If `model_name` not in map, reject the request or require an explicit override.
- **Rounding**: Keep internal cents; present as USD with two decimals.

---

### 10) Returning balance with minimal surface changes

- The API/resource layer reads `BillingContext.get()` after orchestrations finish and enriches the HTTP response with `billing` info, including `balance` (from the `Balance` model).
- Because the proxy centralizes everything, endpoint and orchestrator method signatures do not change.

This solidifies Plan A as the single integration approach: wrap the LLM client once; refactor function-scoped client construction where necessary; model is inferred automatically by the proxy to avoid duplication.

---

### 11) Dedicated balance endpoint

- **File**: `resources/users.py`
- **Route**: `GET /users/me/balance`
- **Auth**: Required (uses the same auth dependency that resolves the current user)
- **Purpose**: Provide the frontend with a lightweight way to fetch the current balance without triggering an LLM call.
- **Response shape**:
```json
{"balance": { "balance_cents": 98, "balance_usd": 0.98, "updated_at": "2025-08-14T12:34:56Z" }}
```
- **Caching/validation (optional)**:
  - Support `ETag`/`If-None-Match` or `Last-Modified`/`If-Modified-Since` to allow cheap revalidation. Return `304 Not Modified` when applicable.
- **When the frontend should call**:
  - On app init or after login
  - After a top-up or when receiving 402 Payment Required
  - On tab visibility change or periodic light polling (e.g., every 30–60s) if the balance is shown persistently
- **What not to do**:
  - Do not embed balance in JWT/session claims (it becomes stale quickly)
- **Implementation notes**:
  - Resolve user via auth context using get_or_create pattern (creates new user with default balance if not exists)
  - Load the `User` record and return `balance_usd` (derived)
  - Keep the endpoint thin; all mutation continues to happen via the billing proxy/service

---

### 12) Example: `council_of_sages/orchestrator/moderator.py::distribute_query`

Existing code:
```python
response = await self.distribution_llm.ainvoke(formatted_prompt)
```
With Plan A, this line stays exactly the same. You only wrap the client once in `__init__` as shown above. The proxy handles pre-check, token counting, cost calculation, atomic decrement, idempotency, and pushes billing info to `BillingContext`.

Notes:
- `current_user` is obtained from a contextvar set by FastAPI auth middleware/dependency.
- The proxy infers the model from the wrapped `base_llm`; there is no need to pass `model_name` again.
- For function-scoped constructions, see the note in Section 5 and refactor accordingly.

---

### 13) Implementation checklist

- **models**:
  - `models/user.py` (balance in cents, default 100; `BaseModel, AsyncDocument`, string id)
  - `models/usage_event.py` with unique index `(user_internal_id, request_id)`
- **lib/billing**:
  - `costs.py` (pricing map using Decimal + getters)
  - `token_count.py` (vendor-aware counting + fallback)
  - `calculator.py` (pure cost computation returning integer cents)
  - `service.py` (internals used by the proxy for token counting, cost, atomic update, and logging)
- **lib/auth**:
  - `context.py` (define `current_user_id_var: ContextVar[str | None]`, and optionally a `current_request_id_var`)
  - Update `lib/auth/dependencies.py` to set these ContextVars inside `get_current_user_id`
- **resources**:
  - `users.py` with `GET /users/me/balance` to retrieve the current user's balance
  - Endpoints remain unchanged aside from constructing/using the wrapped LLM instance
- **types.py**:
  - Add required models:
    - `Balance`: `balance_cents: int`, `balance_usd: float`, `updated_at: datetime`
    - `BillingInfo`: `model_name: str`, `input_tokens: int`, `output_tokens: int`, `cost_cents: int`, `balance: Balance`
- **LLM integration: Centralized proxy (Plan A)**:
  - `lib/billing/billing_llm_proxy.py` with `BillingLLMProxy` that:
    - Resolves current user via a `ContextVar` set by FastAPI auth dependency
    - Executes underlying client calls (`invoke`/`ainvoke`/`stream` as needed)
    - Extracts `response_metadata` to compute tokens and final cost
    - Atomically decrements the user's balance and logs a `UsageEvent`
    - Ensures idempotency via `(user_internal_id, request_id)`
    - Exposes billing info via a `BillingContext` to enrich HTTP responses without signature changes
  - Model inference from the wrapped client (e.g., `getattr(base_llm, "model", None)`); raise clear error if not set
  - Vendor detection to select the right tokenizer/counting strategy; fall back to pricing map
- **Orchestrator updates (no call-site changes)**:
  - Construct LLMs once and wrap with `BillingLLMProxy` during initialization; example in `council_of_sages/orchestrator/moderator.py`:
    - Keep existing call sites like `await self.distribution_llm.ainvoke(...)` unchanged
    - For function-scoped LLM constructions (e.g., tools), refactor to inject a pre-wrapped instance or wrap before use
- **Returning balance with minimal surface changes**:
  - After orchestrations, the API/resource layer reads from `BillingContext.get()` and enriches responses with `billing` info including `balance`
  - Endpoint and orchestrator method signatures remain unchanged due to the proxy
- **Dedicated balance endpoint**:
  - `resources/users.py` with `GET /users/me/balance`
  - Auth required; resolve user via get_or_create
  - Response shape: `{ "balance_cents": int, "balance_usd": float, "updated_at": ISO8601 }`
  - Optional caching/validation support with `ETag` or `Last-Modified`
