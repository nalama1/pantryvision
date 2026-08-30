# Implementation Plan: Manage Products (Update + Soft Delete)

## Overview

Implement Update and soft-Delete for products, plus the frontend controls that
drive them, following the design. Backend is Python 3.12 (boto3), frontend is
React/TypeScript, infrastructure is CloudFormation (Option A: a new
`pantryvision-manage-api` RestApi). Soft delete uses a conditional
`dynamodb:UpdateItem` (no `DeleteItem`, no S3 access); update only SETs the four
editable fields; `list-products` gains a `FilterExpression` that excludes
soft-deleted records.

Conventions to follow throughout:

- **Shared `backend/common/` module is the single source of truth** for the
  `CORS_HEADERS` dict and `build_error_response(status_code, error_code, message)`.
  These were byte-for-byte duplicated across `save-product` and `list-products`;
  they are now defined once in `backend/common/responses.py` and imported by every
  Lambda (`from common.responses import CORS_HEADERS, build_error_response`).
  Each Lambda keeps its own `build_success_response` because the success body
  differs per Lambda (full record vs. list vs. `{productId}`). This is a DRY
  cleanup with **no behavior change** — the moved code is verbatim, same logging
  (WARNING for status < 500, ERROR for status >= 500).
- **Packaging copies `backend/common/` into every deployment zip** (Option B: no
  Lambda Layer, no CloudFormation change). At runtime a Lambda only sees what is
  inside its own zip, so each zip's root MUST contain both the handler and the
  `common/` package for the `from common.responses import ...` to resolve.
- Least privilege: `update-product` and `delete-product` execution roles get only
  `dynamodb:UpdateItem` on the products table ARN (plus `AWSLambdaBasicExecutionRole`).
- Soft delete preserves the S3 image and every non-deletion attribute; update
  preserves `productId`, `imageKey`, `createdAt`, `quantity`, `unit`.
- Backend property tests use pytest + Hypothesis (100+ iterations) with moto/stubbed
  DynamoDB. Frontend tests use Vitest.

## Tasks

- [x] 1. Create the shared `backend/common/` module (DRY source of truth)
  - [x] 1.1 Create the shared response module (`backend/common/__init__.py`, `backend/common/responses.py`)
    - Create `backend/common/__init__.py` (empty package marker) so `common` is importable
    - Create `backend/common/responses.py` containing the single shared `CORS_HEADERS`
      dict and `build_error_response(status_code: int, error_code: str, message: str) -> dict`,
      moved **verbatim** from the existing handlers (same shape, same logging behavior:
      `logging.WARNING` for status < 500, `logging.ERROR` for status >= 500)
    - Use type hints, PEP 8, English comments explaining the "why" (single source of
      truth for CORS + error responses; supports the no-PII logging property)
    - No behavior change versus the existing inline copies
    - _Requirements: 6.4_ (supports the no-PII logging property 8.5 indirectly, since
      error logging now lives in one audited place)

  - [x]* 1.2 Write unit tests for `backend/common/responses.py`
    - Assert `build_error_response` returns the correct shape (`statusCode`, `headers`
      == `CORS_HEADERS`, JSON `body` with `error` and `message`)
    - Assert `CORS_HEADERS` contains `Access-Control-Allow-Origin: *`,
      `Content-Type: application/json`, and the `Access-Control-Allow-Headers` value
    - Assert it logs at WARNING for status < 500 and ERROR for status >= 500 (caplog)
    - pytest (frontend Vitest is not used for Python)
    - _Requirements: 6.4, 8.5_

- [x] 2. Implement the `update-product` Lambda
  - [x] 2.1 Create the update-product handler (`backend/update-product/handler.py`)
    - **Import `CORS_HEADERS` and `build_error_response` from `backend/common`**
      (`from common.responses import CORS_HEADERS, build_error_response`) instead of
      redefining them
    - Module-level `dynamodb = boto3.resource("dynamodb")`, `table = dynamodb.Table(TABLE_NAME)`; read `TABLE_NAME` from env
    - Implement `parse_and_validate_payload(body) -> tuple[dict | None, dict | None]`:
      `productId` non-empty string else `MISSING_PARAMS`; `productName` required and
      non-empty after trim else `MISSING_PARAMS`, then > 200 chars → `INVALID_PARAMS`;
      `brand` > 100 / `presentation` > 100 → `INVALID_PARAMS`; `expirationDate` empty
      allowed, else must match `^\d{4}-\d{2}-\d{2}$` and parse via
      `datetime.strptime` → else `INVALID_DATE`; returns trimmed editable fields
    - Implement `update_product(product_id, fields) -> dict`: `table.update_item`
      SETting only the four editable fields with
      `ConditionExpression="attribute_exists(productId)"` and `ReturnValues="ALL_NEW"`;
      map `ConditionalCheckFailedException` → 404 `NOT_FOUND`; return `Attributes`
    - Implement **local** `build_success_response(record) -> dict` returning HTTP 200
      with the full updated record and `CORS_HEADERS`
    - `lambda_handler`: parse JSON (`INVALID_JSON` on failure), validate, update, build
      response; catch `ClientError`/`Exception` → 500 `INTERNAL_ERROR`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11, 6.4_

  - [x]* 2.2 Write property test for update field preservation
    - **Property 1: Update preserves immutable and untouched fields**
    - **Validates: Requirements 1.1, 1.3, 1.4**

  - [x]* 2.3 Write property test for update rejection
    - **Property 2: Invalid update payloads are rejected with the correct code and never mutate the record**
    - **Validates: Requirements 1.5, 1.6, 1.7, 1.11**

  - [x]* 2.4 Write unit tests for update-product edge cases
    - `INVALID_JSON` on malformed body (Req 1.9); `404 NOT_FOUND` when the conditional
      update raises `ConditionalCheckFailedException` (Req 1.8); boundary values
      (`productName` 200 ok / 201 `INVALID_PARAMS`; empty `expirationDate` accepted)
    - _Requirements: 1.8, 1.9, 1.11_

- [x] 3. Implement the `delete-product` Lambda (soft delete)
  - [x] 3.1 Create the delete-product handler (`backend/delete-product/handler.py`)
    - **Import `CORS_HEADERS` and `build_error_response` from `backend/common`**
      (`from common.responses import CORS_HEADERS, build_error_response`) instead of
      redefining them
    - Same module-level client setup; read `TABLE_NAME` from env; import no S3 client
    - Implement `parse_and_validate_payload(body) -> tuple[str | None, dict | None]`:
      `productId` must be a `str` with `1 <= len <= 256` else `400 MISSING_PARAMS`
    - Implement `soft_delete_product(product_id) -> None`: `table.update_item` with
      `SET #d = :true, #da = :now`, names `{"#d":"deleted","#da":"deletedAt"}`, values
      `{":true": True, ":now": <UTC ISO8601>}` (produced via
      `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`),
      `ConditionExpression="attribute_exists(productId)"`; map
      `ConditionalCheckFailedException` → 404 `NOT_FOUND`; retry transient
      `ClientError`s up to 3 total attempts (never retry conditional/validation errors);
      after retries exhausted → 500 `INTERNAL_ERROR`
    - Implement **local** `build_success_response(product_id) -> dict` returning HTTP 200
      with `{"productId": product_id}` and `CORS_HEADERS`
    - `lambda_handler`: parse JSON (`INVALID_JSON`), validate, soft delete, build response
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 6.4, 8.3_

  - [x]* 3.2 Write property test for soft delete attribute setting
    - **Property 3: Soft delete sets the deletion attributes and preserves everything else**
    - **Validates: Requirements 2.1, 2.2**

  - [x]* 3.3 Write property test for soft delete idempotence
    - **Property 4: Soft delete is idempotent-safe**
    - **Validates: Requirements 2.1, 2.6**

  - [x]* 3.4 Write property test for no-PII logging
    - **Property 6: Logs never contain PII or credentials**
    - **Validates: Requirements 1.10, 2.9, 8.5**

  - [x]* 3.5 Write unit tests for delete-product edge cases
    - `INVALID_JSON` (Req 2.7); `404 NOT_FOUND` on conditional failure (Req 2.6);
      retry path: transient error twice then success (Req 2.8), transient error on all
      3 attempts → 500 (Req 2.9); `productId` length 256 ok / 257 `MISSING_PARAMS`
    - _Requirements: 2.5, 2.6, 2.7, 2.8, 2.9_

- [x] 4. Modify the `list-products` Lambda (exclude soft-deleted + DRY refactor)
  - [x] 4.1 Add the soft-delete filter to `list-products` (`backend/list-products/handler.py`)
    - Add a `FilterExpression` to the scan(s) in `scan_all_products()`:
      `Attr("deleted").not_exists() | Attr("deleted").eq(False)`, applied to the initial
      scan and every paginated follow-up scan
    - Keep enrichment, sort, and response shape unchanged
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 4.2 Refactor `list-products` to import shared response helpers (DRY cleanup)
    - Replace the local `CORS_HEADERS` and `build_error_response` with
      `from common.responses import CORS_HEADERS, build_error_response`; remove the
      local duplicate definitions
    - Keep the local `build_success_response` (returns the enriched list)
    - No-behavior-change refactor: existing `list-products` tests MUST still pass.
      `list-products` is repackaged anyway for the filter change (4.1), so picking up
      the shared module here costs no extra deploy
    - _Requirements: 6.4_

  - [x]* 4.3 Write property test for the list-products soft-delete filter
    - **Property 5: list-products excludes deleted and includes legacy/undeleted records**
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 4.4 Refactor `save-product` to import shared response helpers (OPTIONAL, decide before running)
    - Replace `save-product`'s local `CORS_HEADERS` and `build_error_response` with
      `from common.responses import CORS_HEADERS, build_error_response` for full
      consistency; keep its local `build_success_response`
    - **Optional / low-risk only.** `save-product` is not otherwise touched by this
      feature, so applying this requires repackaging and redeploying an untouched
      Lambda. Skip if you prefer to leave `save-product` for a follow-up; if applied,
      `save-product.zip` MUST be repackaged with `common/` (see 6.1) and existing
      `save-product` tests must still pass
    - _Requirements: 6.4_

- [x] 5. Checkpoint - Verify backend
  - Ensure all backend code, the shared module, and property/unit tests pass, ask the user if questions arise.

- [x] 6. Package and infrastructure
  - [x] 6.1 Package Lambda deployment artifacts (copy `common/` into each zip)
    - Build `backend/update-product.zip`, `backend/delete-product.zip`, and the
      repackaged `backend/list-products.zip` so that **each zip's root contains BOTH
      the handler (`handler.py`) AND the `common/` package** (`common/__init__.py`,
      `common/responses.py`) — Lambda only sees what is inside its own zip, so
      `from common.responses import ...` resolves at runtime (Option B, no Layer,
      no CloudFormation change)
    - If task 4.4 was applied, repackage `backend/save-product.zip` the same way
      (handler + `common/`)
    - Upload the zips to the deployment bucket location referenced by the templates
    - _Requirements: 6.1, 6.4_

  - [x] 6.2 Create the manage-products CloudFormation template (`infra/lambda-manage-products.yaml`)
    - Follow the `lambda-save-product.yaml` pattern (Option A: one new RestApi
      `pantryvision-manage-api`, REGIONAL)
    - Two least-privilege execution roles: `update-product-execution-role` and
      `delete-product-execution-role`, each `AWSLambdaBasicExecutionRole` + inline
      `dynamodb:UpdateItem` on the products table ARN only (no `DeleteItem`, no `s3:*`)
    - Two Lambda functions (python3.12, `handler.lambda_handler`, 128 MB, 10 s timeout,
      `TABLE_NAME` env var, code from the deployment bucket at
      `backend/update-product.zip` / `backend/delete-product.zip`)
    - Resources `/update-product` and `/delete-product`, each with a `POST` method
      (`AWS_IAM`, `AWS_PROXY`) and an `OPTIONS` method (`NONE`, `MOCK` CORS preflight)
    - Two `AWS::Lambda::Permission` for API Gateway invoke; one `AWS::ApiGateway::Deployment`
      (DependsOn all four methods); outputs `ManageApiEndpoint`, `ManageApiId`, function ARNs
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 8.1, 8.2, 8.3, 8.4_

  - [x] 6.3 Extend `infra/cognito-identity-pool.yaml` for the new endpoints
    - Add a `ManageApiId` parameter and two `execute-api:Invoke` resource ARNs for
      `.../POST/update-product` and `.../POST/delete-product` so SigV4-signed calls
      are not rejected with 403
    - _Requirements: 7.1, 7.2_

  - [x]* 6.4 Validate infrastructure templates
    - `aws cloudformation validate-template` on the new template; assert the IAM policies
      contain only `dynamodb:UpdateItem` on the table ARN and no `DeleteItem` / `s3:*`
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 7. Frontend service layer
  - [x] 7.1 Create `manageProductService.ts` (`frontend/src/services/manageProductService.ts`)
    - Define `UpdateProductFields`, `ManageProductErrorCode`, `ManageProductError`
    - Implement `updateProduct(productId, fields)` (POST `/update-product`, 30s
      AbortController timeout) and `deleteProduct(productId)` (POST `/delete-product`,
      10s timeout) via `signedFetch`; map non-2xx and timeouts to `ManageProductError`
    - Read the base URL from `VITE_MANAGE_API_ENDPOINT`
    - _Requirements: 4.3, 4.4, 5.4, 5.6, 7.2_

  - [x]* 7.2 Write service tests for `manageProductService.ts`
    - Mock `signedFetch`; assert URL/method/body, 2xx parses record, non-2xx raises
      `ManageProductError` with mapped code, and a simulated timeout raises the error
    - _Requirements: 4.4, 4.6, 5.6, 5.8_

- [x] 8. Frontend edit flow
  - [x] 8.1 Create the `EditForm` modal (`frontend/src/components/EditForm.tsx`)
    - Reuse the `ReviewForm` field pattern, pre-filled from the selected product;
      client-side validation (productName required after trim ≤ 200 chars); on submit
      disable control + show loading; success closes, error keeps form open with values
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x]* 8.2 Write EditForm interaction tests
    - Empty/whitespace name blocks submit (Req 4.7); > 200 chars blocks (Req 4.8);
      success closes and updates card (Req 4.5); error retains values, re-enables submit (Req 4.6)
    - _Requirements: 4.5, 4.6, 4.7, 4.8_

- [x] 9. Frontend delete flow
  - [x] 9.1 Create the `DeleteConfirmation` dialog (`frontend/src/components/DeleteConfirmation.tsx`)
    - Accessible modal (`role="dialog"`, `aria-modal="true"`, `aria-labelledby`) showing
      the product name; focus moves in on open, is trapped while open, and returns to the
      Delete control on close; confirm shows loading + disables controls; success/error
      handling per design
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [x]* 9.2 Write DeleteConfirmation tests
    - Focus moves in and dialog is modal showing the name (Req 5.2, 5.3); focus trapped;
      cancel closes and restores focus (Req 5.5); confirm loading/disabled (Req 5.6),
      success removes card (Req 5.7), error keeps card and re-enables (Req 5.8)
    - _Requirements: 5.2, 5.3, 5.5, 5.6, 5.7, 5.8_

- [x] 10. Wire Edit and Delete into the Inventory Dashboard
  - [x] 10.1 Add Edit and Delete controls and overlay state to `InventoryDashboard` / `ProductCard`
    - Add focusable Edit and Delete `<button>`s with accessible names on each card;
      hold `editingProduct` / `deletingProduct` state; on edit success replace the card
      in place, on delete success remove the card
    - _Requirements: 4.1, 4.5, 5.1, 5.7_

  - [x]* 10.2 Write ProductCard accessibility tests
    - Edit and Delete controls are focusable buttons with accessible names
    - _Requirements: 4.1, 5.1_

- [x] 11. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP.
- The shared `backend/common/` module is the single source of truth for `CORS_HEADERS`
  and `build_error_response`; packaging (task 6.1) copies it into each Lambda zip so the
  imports resolve at runtime (Option B — no Lambda Layer, no CloudFormation change).
- Task 4.4 (refactor `save-product` to use `common/`) is intentionally optional: it forces
  repackaging/redeploying an otherwise-untouched Lambda, so decide before running it.
- Backend property tests validate the design's Correctness Properties (pytest + Hypothesis,
  100+ iterations, moto/stubbed DynamoDB); unit tests cover edge cases; frontend uses Vitest.
- Least-privilege IAM (`dynamodb:UpdateItem` only) and soft-delete semantics (no `DeleteItem`,
  no S3 access) are unchanged by the DRY refactor.
- Each task references specific requirements for traceability; checkpoints ensure incremental validation.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1", "3.1", "4.1", "7.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "3.2", "3.3", "3.4", "3.5", "4.2", "6.2", "6.3", "7.2", "8.1", "9.1"] },
    { "id": 3, "tasks": ["4.3", "4.4", "8.2", "9.2", "10.1"] },
    { "id": 4, "tasks": ["6.1", "6.4", "10.2"] }
  ]
}
```
