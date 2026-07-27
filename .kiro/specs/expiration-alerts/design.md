# Design Document

## Overview

The `expiration-alerts` feature adds a daily, fully automated check that scans the existing `pantryvision-products` DynamoDB table, classifies each product as `Expiring_Product` (expiring within the next 7 days) or `Expired_Product` (already past its expiration date), and — if any such products exist — sends a single consolidated email via Amazon SES to the household owner.

The feature is entirely backend-only: a new AWS Lambda function (`check-expiring-products`), triggered once per day by an Amazon EventBridge scheduled rule, with no changes to the frontend, no AI/Bedrock involvement, and no schema changes to the existing product record. It reuses the existing `pantryvision-products` table and follows the same infrastructure-as-code and IAM least-privilege patterns already established in `/infra` for the other Lambda functions (`lambda-list-products.yaml`, `lambda-extract.yaml`, etc.).

## Architecture

```mermaid
flowchart LR
    EB["Amazon EventBridge<br/>Daily_Schedule (cron, UTC)"] -->|invokes| L["AWS Lambda<br/>check-expiring-products<br/>(Expiration_Checker)"]
    L -->|dynamodb:Scan<br/>(paginated)| DDB[("Amazon DynamoDB<br/>pantryvision-products")]
    L -->|ses:SendEmail<br/>(if Alert_Batch non-empty)| SES["Amazon SES<br/>(sandbox mode)"]
    SES -->|Alert_Email| Inbox["Recipient_Address<br/>(verified identity)"]
    L -->|structured logs| CW["Amazon CloudWatch Logs"]
```

**Flow:**
1. EventBridge triggers the Lambda once every 24 hours (daily cron, UTC).
2. The Lambda validates that `ALERT_SENDER_EMAIL` and `ALERT_RECIPIENT_EMAIL` are configured; if not, it aborts and logs the misconfiguration before touching DynamoDB.
3. The Lambda scans the `pantryvision-products` table (following pagination via `LastEvaluatedKey`), retrying up to 3 attempts on transient scan failures.
4. Each product is classified against `Current_Date` (UTC) into `Expiring_Product`, `Expired_Product`, or excluded (no `expirationDate`).
5. If the resulting `Alert_Batch` is non-empty, the Lambda builds the email body and sends it via SES, retrying transient SES failures up to 2 additional times (3 attempts total) with a minimum 2-second delay between attempts, and not retrying non-transient failures.
6. The Lambda logs counts and delivery status to CloudWatch, never including product images, email addresses, or credentials.

This design keeps the architecture 100% serverless and pay-per-use: EventBridge and Lambda are billed per invocation, DynamoDB is already on-demand, and SES is billed per email — no idle compute, consistent with the project's cost optimization principles.

## Components and Interfaces

### Lambda Function: `check-expiring-products`

Single-responsibility handler split into small, independently testable functions, following the same style as `backend/list-products/handler.py`.

```python
def lambda_handler(event, context) -> dict:
    """Entry point invoked by the Daily_Schedule EventBridge rule."""

def get_alert_config() -> AlertConfig:
    """Reads ALERT_SENDER_EMAIL / ALERT_RECIPIENT_EMAIL / TABLE_NAME from env.
    Raises ConfigurationError if sender or recipient is missing/blank."""

def scan_products(table) -> list[dict]:
    """Scans the Products_Table across all pages. Retries up to 3 total
    attempts on transient DynamoDB errors, with a short backoff between
    attempts. Raises ScanFailedError after exhausting retries."""

def classify_products(products: list[dict], current_date: date) -> AlertBatch:
    """Pure function: classifies each product record as Expiring_Product,
    Expired_Product, or excluded (missing expirationDate). Returns an
    AlertBatch (list of classified entries). No I/O — fully unit/property
    testable in isolation."""

def build_email_body(alert_batch: AlertBatch) -> tuple[str, str]:
    """Pure function: builds (subject, body) text listing product name,
    expiration date, and classification for every entry in the batch."""

def send_alert_email(ses_client, sender: str, recipient: str, subject: str, body: str) -> DeliveryResult:
    """Sends the Alert_Email via SES. Retries up to 2 additional times
    (3 attempts total) on transient errors with >=2s delay between
    attempts; does not retry on non-transient errors. Returns a
    DeliveryResult (status: sent/failed, failure_reason: str | None)."""

def log_run_summary(expiring_count: int, expired_count: int, status: str, failure_reason: str | None = None) -> None:
    """Logs a single structured summary line to CloudWatch. Never includes
    email addresses, image keys, or product-level PII beyond product name
    counts."""
```

`lambda_handler` orchestrates these functions in order and is the only place with control flow branching (config check → scan → classify → conditionally build+send → log). Each other function has a single responsibility and no hidden shared state, which is what makes `classify_products` and `build_email_body` cleanly property-testable as pure functions.

### Error/Retry Semantics Summary

| Step | Failure type | Retries | On exhaustion |
|---|---|---|---|
| Config read | missing env var | 0 | Abort run, log misconfiguration, no scan |
| DynamoDB scan | any `ClientError` | 3 total attempts | Abort run, no email sent, table unchanged |
| SES send | transient (throttling, 5xx) | 2 additional (3 total), >=2s delay | Log failure, no further retry this run |
| SES send | non-transient (unverified identity, malformed request) | 0 | Log failure immediately, no retry |
| Unhandled exception (any stage) | n/a | 0 | Log error, terminate, no partial/duplicate email |

Transient vs. non-transient SES classification is done by inspecting the `ClientError` code: throttling/`5xx`-style codes (e.g., `Throttling`, `ServiceUnavailable`) are treated as transient; identity/validation codes (e.g., `MessageRejected`, `MailFromDomainNotVerified`) are treated as non-transient.

## Data Models

No schema changes. The feature reuses the existing product record shape stored in `pantryvision-products`:

```python
# Existing product record shape (read-only for this feature)
{
    "productId": str,          # partition key
    "productName": str,
    "brand": str,
    "presentation": str,
    "expirationDate": str,     # ISO 8601 date "YYYY-MM-DD"; may be absent
    "imageKey": str,           # S3 object key; never logged or emailed
    "quantity": int,
    "unit": str,
}
```

New in-memory-only types introduced by this feature (not persisted):

```python
class AlertConfig(TypedDict):
    sender_address: str
    recipient_address: str
    table_name: str

class ClassifiedProduct(TypedDict):
    product_name: str
    expiration_date: str
    classification: str  # "Expiring_Product" | "Expired_Product"

AlertBatch = list[ClassifiedProduct]

class DeliveryResult(TypedDict):
    status: str                 # "sent" | "not-needed" | "failed"
    failure_reason: str | None
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Classification correctness by day offset

For any current date `D` and any integer offset `N` (positive, negative, or zero), a product whose `expirationDate` equals `D + N days` is classified as `Expiring_Product` if and only if `0 <= N <= 7`, and as `Expired_Product` if and only if `N < 0`.

**Validates: Requirements 1.3, 1.4**

### Property 2: Products without expirationDate are always excluded

For any list of product records containing a mix of records with and without an `expirationDate` attribute, none of the records missing `expirationDate` appear in the resulting `Alert_Batch`, and every other record in the list is still classified correctly.

**Validates: Requirements 1.5**

### Property 3: Full pagination coverage

For any sequence of mocked DynamoDB scan responses split across an arbitrary number of pages (via `LastEvaluatedKey`), `scan_products` returns the exact concatenation of all items across all pages, regardless of how the items are distributed among pages.

**Validates: Requirements 1.1**

### Property 4: DynamoDB scan retry bound

For any sequence of injected transient DynamoDB errors, `scan_products` attempts the scan at most 3 times total before raising a `ScanFailedError`, and never sends an Alert_Email when the scan ultimately fails.

**Validates: Requirements 1.6, 2.6**

### Property 5: Empty batch never triggers an email

For any list of product records where every record is either missing `expirationDate` or has an `expirationDate` outside the expiring/expired window, the resulting `Alert_Batch` is empty and `send_alert_email` is never invoked.

**Validates: Requirements 2.4**

### Property 6: Non-empty batch produces exactly one complete email

For any non-empty `Alert_Batch`, `send_alert_email` is invoked exactly once per run, and the built email body contains the product name, expiration date, and classification label for every entry in the batch.

**Validates: Requirements 2.2, 2.3**

### Property 7: Classification is stateless across runs

For any fixed list of product records and fixed current date, calling `classify_products` twice in succession (simulating two consecutive daily runs with no external state) produces identical `Alert_Batch` results both times.

**Validates: Requirements 2.5**

### Property 8: SES retry bound and backoff for transient failures

For any sequence of injected transient SES errors, `send_alert_email` attempts the send at most 3 times total, waits at least 2 seconds between consecutive attempts, and returns a `failed` `DeliveryResult` only after exhausting all attempts.

**Validates: Requirements 2.7, 3.3**

### Property 9: Non-transient SES failures never retry

For any injected non-transient SES error code (e.g., `MessageRejected`, `MailFromDomainNotVerified`), `send_alert_email` makes exactly one send attempt and immediately returns a `failed` `DeliveryResult` with no retry.

**Validates: Requirements 3.4**

### Property 10: Access-denied failures terminate cleanly without partial output

For any injected `AccessDenied`-style `ClientError` raised from either the scan or the send call, the run terminates without sending an Alert_Email and without raising an unhandled exception out of `lambda_handler`, and a failure is logged.

**Validates: Requirements 4.5, 5.3**

### Property 11: Run summary log reflects actual outcome

For any generated set of product records and any mocked SES outcome (success or a specific failure reason), the final summary log entry's `expiring_count` and `expired_count` equal the actual number of `Expiring_Product` and `Expired_Product` entries in the batch, and its `status` field equals `sent`, `not-needed`, or `failed` consistently with what actually happened, including the specific SES failure reason when `status == "failed"`.

**Validates: Requirements 5.1, 5.2**

### Property 12: No log entry ever leaks sensitive values

For any generated product data, sender/recipient email addresses, and image keys (including values that look like emails, S3 keys, or AWS credential strings such as `AKIA...`), none of the strings passed to the logger anywhere in the pipeline contain the sender address, recipient address, any `imageKey` value, or a credential-like substring.

**Validates: Requirements 2.6, 3.5, 4.5, 5.4**

## Error Handling

- **Missing configuration (Req 2.8):** `get_alert_config` raises `ConfigurationError` before any DynamoDB call is made; `lambda_handler` catches it, logs a misconfiguration message (naming which variable is missing, not its value), and returns without scanning.
- **DynamoDB scan failure (Req 1.6, 2.6):** `scan_products` retries transient `ClientError`s up to 3 total attempts. On exhaustion, it raises `ScanFailedError`; `lambda_handler` catches it, logs the failure (error code only, no product data), and returns without sending any email. The table is never written to by this feature, so it is inherently left unchanged.
- **SES transient failure (Req 3.3):** `send_alert_email` retries up to 2 additional times (3 attempts total) with `time.sleep(2)` (or longer, via exponential backoff) between attempts, then returns `DeliveryResult(status="failed", failure_reason=...)`.
- **SES non-transient failure (Req 3.4):** Detected by SES error code; `send_alert_email` returns `failed` immediately without any retry loop iteration.
- **IAM/permission failures (Req 4.5):** Both DynamoDB and SES calls can raise `AccessDeniedException`/`AccessDenied`; these are treated as non-retryable, logged (excluding any credential values — none are ever available to the code since it uses the execution role, not static keys), and the run terminates without partial output.
- **Any unhandled exception (Req 5.3):** `lambda_handler` wraps the full scan→classify→send pipeline in a top-level `try/except Exception`, logs the error via `logger.exception(...)`, and returns a failure result without a partial or duplicate `send_email` call (the send step only ever executes once per invocation, guarded by the non-empty-batch check).
- **Logging discipline (Req 5.4):** All log calls use structured, pre-aggregated values (counts, status strings, error codes) — never raw product dicts, `imageKey` values, or the configured email addresses. This is enforced by convention in `log_run_summary` and validated by Property 12.

## Testing Strategy

**Dual testing approach**, consistent with the project's PBT guidance:

- **Unit tests** (example-based) cover:
  - Requirement 2.8 configuration validation (missing sender / missing recipient / both missing / both present).
  - Requirement 3.1/3.2 SES call wiring (`Source`/`Destination` set from env-derived config, not hardcoded).
  - Requirement 3.6 is a deployment checklist item (manual SES identity verification in sandbox mode), not code-testable.
  - Requirement 4.1/4.2 are verified via a CloudFormation template review of `infra/lambda-check-expiring.yaml` (IAM policy scoped to the table ARN and sender identity ARN; no hardcoded secrets), not a unit test.
  - Requirement 4.3 (60s for 10,000 records) is covered by a performance/integration test with a generated 10,000-item dataset and mocked AWS clients, asserting wall-clock time under 60 seconds.
  - Requirement 4.4 (no Bedrock invocation) is covered by a static check that no Bedrock client is created or called anywhere in the module.

- **Property tests** (property-based, minimum 100 iterations each) cover Properties 1–12 above, using a property-based testing library for Python (`hypothesis`), with `boto3` DynamoDB/SES clients mocked (e.g., via `unittest.mock` or `moto`) so tests remain fast and cost-free. Each test is tagged with a comment referencing its design property, in the format:

  ```python
  # Feature: expiration-alerts, Property 1: Classification correctness by day offset
  ```

  Each property is implemented as a single `hypothesis`-based test function, configured to run at least 100 examples (`@settings(max_examples=100)`), generating random dates, offsets, product lists (with/without `expirationDate`), and injected error sequences as appropriate to the property.

- **Integration tests** cover the full `lambda_handler` wired against `moto`-mocked DynamoDB and SES to confirm end-to-end wiring (scan → classify → email → log) for a small number of representative scenarios (empty inventory, mixed inventory, scan failure, SES failure), complementing the pure-function property tests above.
