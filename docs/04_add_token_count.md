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

Example (conceptual):
```python
class User(BaseModel, AsyncDocument):
    id = StringField(primary_key=True, default=uuid_field("USR_"))
    user_id = StringField(required=True, unique=True)
    balance_cents = IntField(required=True, default=100)  # 1 USD
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
```
1.1) usage_event in mongo

- **File**: `models/usage_event.py`
- **Purpose**: Auditing and analytics.
- **Fields**: `user_id`, `request_id`, `model_name`, `input_tokens`, `output_tokens`, `cost_cents`, `provider_request_id`, `status`, `created_at`.


---

### 2) Pre-request balance check

- **Where**: FastAPI dependency or a small middleware-like helper used by LLM endpoints.
- **Behavior**:
  - Load `User` by `user_id` from auth context using get_or_create pattern (create with default balance if new user).
  - If `balance_cents <= 0`, return 402 Payment Required (or 403 with domain error) before executing the LLM call.
- **Rationale**: Prevents unnecessary spending when the user is clearly out of balance. We will still deduct post-request to reduce repetitive code and avoid partial updates.

---

### 3) Pricing map: per-model, input/output prices

- **File**: `lib/billing/costs.py`
- **Format**: Prices in USD per 1K tokens. Use integer microcents or cents for storage; convert carefully.
- **Structure**:
```python
MODEL_PRICING = {
    # Example values. Replace with real ones from providers.
    "gpt-4o-mini": {
        "input_usd_per_1k": 0.1500,
        "output_usd_per_1k": 0.6000,
        "tokenizer": "openai",
    },
    "gpt-4o": {
        "input_usd_per_1k": 5.0000,
        "output_usd_per_1k": 15.0000,
        "tokenizer": "openai",
    },
    "claude-3-5-haiku-20241022": {
        "input_usd_per_1k": 0.2500,
        "output_usd_per_1k": 1.2500,
        "tokenizer": "anthropic",
    },
}
```
---

### 4) Reusable billing utilities

- **Files**:
  - `lib/billing/token_count.py`: vendor-aware token counting
  - `lib/billing/calculator.py`: cost computation
  - `lib/billing/service.py`: high-level orchestration used by endpoints

- **Token counting** (`lib/billing/token_count.py`):
  - `count_input_tokens(model_name, prompt_or_messages) -> int`
  - `count_output_tokens(model_name, response_text_or_content, response_metadata) -> int`
  - Prefer vendor tokenizers (e.g., `tiktoken` for OpenAI; Anthropic tokenizer if available).
  - Fallback: heuristic estimator when metadata is missing.

- **Cost calculator** (`lib/billing/calculator.py`):
```python
def calculate_cost_usd(model_name: str, input_tokens: int, output_tokens: int) -> float:
    prices = get_model_prices(model_name)
    input_cost = (input_tokens / 1000.0) * prices.input_usd_per_1k
    output_cost = (output_tokens / 1000.0) * prices.output_usd_per_1k
    return round(input_cost + output_cost, 6)
```
  - If storing as cents: convert `usd -> cents` with correct rounding once at the boundary.

- **Billing service** (`lib/billing/service.py`):
  - Public API designed for minimal repetition in endpoints:
```python
class UsageTracker:
    def __init__(self, user: User, model_name: str, input_tokens: int, request_id: str): ...
    def finalize(self, response_metadata: dict, output_text: str | None = None) -> dict:
        # determines output_tokens, computes cost, persists usage log, atomically decrements balance
        # returns dict with cost breakdown and current balance
```
  - Factory/helper:
```python
def start_usage(user: User, model_name: str, prompt_or_messages, request_id: str) -> UsageTracker:
    input_tokens = count_input_tokens(model_name, prompt_or_messages)
    return UsageTracker(user, model_name, input_tokens, request_id)
```
  - **User resolution**: All billing operations should use get_or_create pattern to ensure new users are automatically created with default balance (100 cents = $1.00).
  - Atomic balance update and logging:
    - Create a `UsageEvent` record with: `user_id`, `request_id`, `model_name`, `input_tokens`, `output_tokens`, `cost_cents`, timestamps, and any provider ids.
    - Deduct balance using a single atomic `find_one_and_update` with filter: `{"_id": user.id, "balance_cents": {"$gte": 0}}` and update: `{"$inc": {"balance_cents": -cost_cents}}`.
      - We check `> 0` before the call; here we deduct after the call. If a race drives balance below zero, that is acceptable; the next pre-check will block.

---

### 5) Endpoint integration pattern (minimal repetition)

- **Before request**:
  - Resolve `User` from auth using get_or_create (creates new user with default 100 cents balance if not exists).
  - If `balance_cents <= 0`: return 402.
  - Create `request_id` (idempotency key per logical call) and `tracker = start_usage(user, model_name, prompt_or_messages, request_id)`.

- **Execute LLM**:
  - Call provider SDK.

- **After response**:
  - `result = tracker.finalize(response_metadata=provider_response.meta, output_text=provider_response.text)`
  - Include `result["current_balance_usd"]` (or cents) in the API response payload.

- **Return shape suggestion** (add balance consistently):
```json
{
  "data": { /* original payload */ , current_balance_usd},
}
```

- **Where to put glue code**:
  - A small helper in `resources/_billing.py` that exposes `require_balance_and_start_usage(model_name, prompt_or_messages)` returning `(user, tracker)` for endpoints.
  - This helper should handle the get_or_create logic for users internally.

---

### 6) Calculating cost from response metadata

- **Preferred**: Use provider-returned token counts when available:
  - OpenAI: `usage.prompt_tokens`, `usage.completion_tokens`, and `usage.total_tokens`.
  - Anthropic: `usage.input_tokens`, `usage.output_tokens`.
- **Fallback**:
  - If metadata is missing, count tokens from input and generated text with the vendor tokenizer.
- **Final formula**:
  - `total_cost = input_tokens / 1000 * input_usd_per_1k + output_tokens / 1000 * output_usd_per_1k`
  - Round at the final step, not per component.

---

### 7) Updating and returning balance

- **When**: After the full flow completes (post-response computation), inside `tracker.finalize(...)`.
- **How**: Single atomic decrement; record a `UsageEvent`. This keeps endpoints clean and avoids partial state.
- **Response**: Always include `current_balance_usd` in the returned payload.

---

### 9) Error handling

- **LLM call fails**: Do not deduct. Optionally log a `UsageEvent` with `status = failed` and `cost_cents = 0`.
- **Missing pricing**: If `model_name` not in map, reject the request or require an explicit override.
- **Rounding**: Keep internal cents; present as USD with two decimals.



---

### 13) LLM integration: Centralized proxy (Plan A)

Adopt a single, centralized wrapper so call sites remain unchanged. The proxy will infer the model from the underlying client, so you do not need to pass the model name twice.

- **File**: `lib/billing/llm_proxy.py`
- **Class**: `BillingLLMProxy`
- **Responsibilities**:
  1. Resolve current user via a `contextvars.ContextVar` set by FastAPI auth dependency.
  2. Execute the underlying client call (`invoke`, `ainvoke`, and optionally `stream`/`astream`).
  3. Extract `response_metadata` to compute tokens and final cost.
  4. Atomically decrement the user's balance and log a `UsageEvent`.
  5. Expose billing info through a `BillingContext` contextvar so the API layer can attach it to the HTTP response without changing orchestrator signatures.

- **Model inference (no duplication)**:
  - The proxy introspects the base client to determine the model name. Common patterns:
    - LangChain OpenAI: `getattr(base_llm, "model", None)`
    - LangChain Anthropic: `getattr(base_llm, "model", None)`
    - OpenAI SDK client wrappers: read from configuration or request kwargs captured during call.
  - If the model cannot be inferred, the proxy will raise a clear error instructing to set a model on the base client. No explicit `model_name` parameter is required by default.

- **Vendor detection**:
  - The proxy maps the inferred model to a vendor (OpenAI, Anthropic, etc.) to select the right tokenizer/counting strategy. Fallbacks to the pricing map when needed.

- **Construction (one-time)**:
```python
from lib.billing.llm_proxy import BillingLLMProxy
from langchain_openai import ChatOpenAI  # example; use your provider

class Moderator:
    def __init__(self, ...) -> None:
        raw_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.distribution_llm = BillingLLMProxy(base_llm=raw_llm)
```

- **Important note about function-scoped LLMs**:
  - If any LLMs are constructed inside functions (e.g., `council_of_sages/orchestrator/tools/philosophical_sage.py`), refactor to construct them once and inject the wrapped instance, or wrap the constructed client before use. Otherwise, the "no call-site changes" guarantee does not hold for those sites.

---

### 14) Example: `council_of_sages/orchestrator/moderator.py::distribute_query`

Existing code:
```python
response = await self.distribution_llm.ainvoke(formatted_prompt)
```
With Plan A, this line stays exactly the same. You only wrap the client once in `__init__` as shown above. The proxy handles pre-check, token counting, cost calculation, atomic decrement, and pushes billing info to `BillingContext`.

Notes:
- `current_user` is obtained from a contextvar set by FastAPI auth middleware/dependency.
- The proxy infers the model from the wrapped `base_llm`; there is no need to pass `model_name` again.
- For function-scoped constructions, see the note in Section 13 and refactor accordingly.

---

### 15) Returning balance with minimal surface changes

- The API/resource layer reads `BillingContext.get()` after orchestrations finish and enriches the HTTP response with `billing` info, including `current_balance_usd`.
- Because the proxy centralizes everything, endpoint and orchestrator method signatures do not change.

This solidifies Plan A as the single integration approach: wrap the LLM client once; refactor function-scoped client construction where necessary; model is inferred automatically by the proxy to avoid duplication.

---

### 16) Dedicated balance endpoint

- **File**: `resources/users.py`
- **Route**: `GET /users/me/balance`
- **Auth**: Required (uses the same auth dependency that resolves the current user)
- **Purpose**: Provide the frontend with a lightweight way to fetch the current balance without triggering an LLM call.
- **Response shape**:
```json
{ "balance_cents": 98, "balance_usd": 0.98, "updated_at": "2025-08-14T12:34:56Z" }
```
- **Caching/validation (optional)**:
  - Support `ETag`/`If-None-Match` or `Last-Modified`/`If-Modified-Since` to allow cheap revalidation. Return `304 Not Modified` when applicable.
- **When the frontend should call**:
  - On app init or after login
  - After a top-up or when receiving 402 Payment Required
  - On tab visibility change or periodic light polling (e.g., every 30–60s) if the balance is shown persistently
  - Do not refetch immediately after LLM requests if those responses already include `billing.current_balance_*`
- **What not to do**:
  - Do not embed balance in JWT/session claims (it becomes stale quickly)
- **Implementation notes**:
  - Resolve user via auth context using get_or_create pattern (creates new user with default balance if not exists)
  - Load the `User` record and return `balance_usd` (derived)
  - Keep the endpoint thin; all mutation continues to happen via the billing proxy/service

### 17) Implementation checklist

- **models**:
  - `models/user.py` (balance in cents, default 100; `BaseModel, AsyncDocument`, string id)
  - `models/usage_event.py` (optional but recommended)
- **lib/billing**:
  - `costs.py` (pricing map + getters)
  - `token_count.py` (vendor-aware counting + fallback)
  - `calculator.py` (pure cost computation)
  - `service.py` (`start_usage`, `UsageTracker.finalize` with atomic update and logging)
- **lib/auth**:
  - `context.py` (define `current_user_id_var: ContextVar[str | None]`)
  - Update `lib/auth/dependencies.py` to set `current_user_id_var` inside `get_current_user_id`
- **resources**:
  - `_billing.py` helper to integrate in endpoints
  - `users.py` with `GET /users/me/balance` to retrieve the current user's balance
  - Update LLM endpoints to follow the 3-call pattern: pre-check → call → finalize
- **types.py**:
  - `BillingInfo` response model (optional) to standardize response shape
  - `BalanceResponse` model (optional) for the balance endpoint
- **LLM integration: Centralized proxy (Plan A)**:
  - `lib/billing/llm_proxy.py` with `BillingLLMProxy` that:
    - Resolves current user via a `ContextVar` set by FastAPI auth dependency
    - Executes underlying client calls (`invoke`/`ainvoke`/`stream` as needed)
    - Extracts `response_metadata` to compute tokens and final cost
    - Atomically decrements the user's balance and logs a `UsageEvent`
    - Exposes billing info via a `BillingContext` to enrich HTTP responses without signature changes
  - Model inference from the wrapped client (e.g., `getattr(base_llm, "model", None)`); raise clear error if not set
  - Vendor detection to select the right tokenizer/counting strategy; fall back to pricing map
- **Orchestrator updates (no call-site changes)**:
  - Construct LLMs once and wrap with `BillingLLMProxy` during initialization; example in `council_of_sages/orchestrator/moderator.py`:
    - Keep existing call sites like `await self.distribution_llm.ainvoke(...)` unchanged
    - For function-scoped LLM constructions (e.g., tools), refactor to inject a pre-wrapped instance or wrap before use
- **Returning balance with minimal surface changes**:
  - After orchestrations, the API/resource layer reads from `BillingContext.get()` and enriches responses with `billing` info including `current_balance_usd`
  - Endpoint and orchestrator method signatures remain unchanged due to the proxy
- **Dedicated balance endpoint**:
  - `resources/users.py` with `GET /users/me/balance`
  - Auth required; resolve user via get_or_create
  - Response shape: `{ "balance_cents": int, "balance_usd": float, "updated_at": ISO8601 }`
  - Optional caching/validation support with `ETag` or `Last-Modified`
