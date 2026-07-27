# Implementation Plan: Inventory Dashboard

## Overview

Implement the list-products endpoint (Lambda + DynamoDB scan + S3 presigned URLs), a new "My Inventory" dashboard view, expiration-based highlighting, and a simple nav bar to switch between Upload and Inventory views. Backend is Python 3.12, frontend is React/TypeScript, infrastructure is CloudFormation.

## Tasks

- [ ] 1. Backend: list-products Lambda handler
  - [ ] 1.1 Create the list-products Lambda handler (`/backend/list-products/handler.py`)
    - Implement `scan_all_products`: scan `Products_Table` via boto3, handling `LastEvaluatedKey` pagination internally to return all items
    - Implement `enrich_with_image_url`: given an item, return a copy with `imageUrl` set to a presigned GET URL (300s expiration, via `s3_client.generate_presigned_url`) when `imageKey` is non-empty, or `None` otherwise; catch and log any per-item presign failure and set `imageUrl` to `None` rather than failing the request
    - Implement `sort_by_expiration`: sort items ascending by `expirationDate`, placing items with an empty `expirationDate` after all items with a non-empty one
    - Implement `lambda_handler`: orchestrate scan → enrich → sort → success response; catch `ClientError` and unexpected exceptions, returning 500 `INTERNAL_ERROR` without leaking details
    - Implement `build_success_response` and `build_error_response` with CORS headers (`Access-Control-Allow-Origin: *`)
    - Read `TABLE_NAME` and `BUCKET_NAME` from environment variables
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6, 2.1, 2.2_

  - [ ]* 1.2 Write property test for scan-and-return behavior
    - **Property 1: Scan returns every stored record**
    - **Validates: Requirements 1.1, 1.4**
    - Use mocked DynamoDB table (e.g., `moto` or a stub) with randomly generated sets of items, including the empty-set case

  - [ ]* 1.3 Write property test for presigned URL enrichment
    - **Property 2: Presigned URL generation depends only on imageKey presence**
    - **Validates: Requirements 1.2, 1.3**
    - Mock `generate_presigned_url`, generate items with a mix of empty/non-empty `imageKey`

  - [ ]* 1.4 Write property test for sort order
    - **Property 3: Sort order is ascending by expiration date with blanks last**
    - **Validates: Requirements 2.1, 2.2**
    - Generate random lists of items with random dates and blank dates

  - [ ]* 1.5 Write property test for CORS headers
    - **Property 4: CORS headers present in every response**
    - **Validates: Requirements 1.6**
    - Cover success, empty-list, and forced-error paths

  - [ ]* 1.6 Write unit tests for edge cases
    - Empty table returns 200 with empty array (Requirements 1.4)
    - DynamoDB scan raising `ClientError` returns 500 `INTERNAL_ERROR` without exposing exception details (Requirements 1.5)

- [ ] 2. Infrastructure: list-products Lambda stack
  - [ ] 2.1 Create Lambda CloudFormation template (`/infra/lambda-list-products.yaml`)
    - Follow the existing `lambda-save-product.yaml` pattern
    - IAM Role: `AWSLambdaBasicExecutionRole` managed policy + inline policy granting `dynamodb:Scan` on the products table ARN only and `s3:GetObject` on the images bucket ARN only
    - Lambda function: Python 3.12, 128MB, 10s timeout, `TABLE_NAME` and `BUCKET_NAME` env vars
    - API Gateway REST API with `GET /list-products` (AWS_PROXY integration, `AuthorizationType: NONE` matching existing temporary setup) and `OPTIONS /list-products` (CORS mock integration)
    - Lambda permission for API Gateway invocation
    - Deployment to `prod` stage
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 3. Checkpoint - Verify backend
  - Ensure all backend code and infrastructure templates are complete, ask the user if questions arise.

- [ ] 4. Frontend: inventory service and expiration helper
  - [ ] 4.1 Create inventory service (`/frontend/src/services/inventoryService.ts`)
    - Define `InventoryProduct` interface, `ListProductsErrorCode` type, and `ListProductsError` class
    - Implement `listProducts()`: GET to `VITE_LIST_API_ENDPOINT`/list-products, parse and return the array on success, throw `ListProductsError` on failure
    - Follow the same pattern as `productService.ts`
    - _Requirements: 3.1_

  - [ ] 4.2 Create expiration classification helper (`/frontend/src/components/InventoryDashboard/expirationStatus.ts`)
    - Implement `getExpirationStatus(expirationDate, today)`: returns `'expired'`, `'expiring-soon'`, or `'normal'` per the design's classification rules
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 4.3 Write property test for expiration classification
    - **Property 6: Expiration classification is correct for any date**
    - **Validates: Requirements 4.1, 4.2, 4.3**
    - Generate random dates relative to a fixed `today`, including boundary days (today, today+7, today+8, yesterday, empty string)

- [ ] 5. Frontend: Inventory Dashboard component
  - [ ] 5.1 Create `InventoryDashboard` component (`/frontend/src/components/InventoryDashboard/InventoryDashboard.tsx`)
    - On mount, call `listProducts()`; manage `loading`, `error`, `products` state
    - Render loading indicator while fetching
    - Render error message with a "Retry" button on failure (re-triggers fetch)
    - Render empty-state message when the array is empty
    - Render a product card per item: image (using `imageUrl` or a placeholder when null), `productName`, `brand`, `presentation`, `expirationDate`, `quantity`/`unit`
    - Apply the CSS class from `getExpirationStatus` to each card container
    - Add `InventoryDashboard.css` for card grid layout and highlight styles (expiring-soon, expired), following existing style conventions in `/frontend/src/styles`
    - Export from `/frontend/src/components/InventoryDashboard/index.ts`, add to `/frontend/src/components/index.ts`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3_

  - [ ]* 5.2 Write property test for product card rendering
    - **Property 5: Rendered product card exposes all required fields and correct image source**
    - **Validates: Requirements 3.2, 3.3**
    - Generate random `InventoryProduct` objects (including null `imageUrl`), render, assert all field values and correct image source are present

  - [ ]* 5.3 Write unit tests for dashboard states
    - Loading indicator shown while fetch is pending (Requirements 3.4)
    - Error message and retry button shown on fetch failure; retry re-triggers the call (Requirements 3.5)
    - Empty-state message shown for an empty array (Requirements 3.6)

- [ ] 6. Frontend: Nav Bar and App wiring
  - [ ] 6.1 Create `NavBar` component (`/frontend/src/components/NavBar/NavBar.tsx`)
    - Accept `activeView` and `onSelectView` props
    - Render "Upload" and "My Inventory" buttons/tabs, marking the active one
    - Add `NavBar.css` following existing header styling conventions
    - Export from `/frontend/src/components/NavBar/index.ts`, add to `/frontend/src/components/index.ts`
    - _Requirements: 5.1_

  - [ ] 6.2 Update `App.tsx` to wire navigation
    - Add `view` state (`'upload' | 'inventory'`), default `'upload'`
    - Render `NavBar` above main content, updating `view` on selection
    - Render existing Upload/extracting/review/done flow when `view === 'upload'`, `InventoryDashboard` when `view === 'inventory'`
    - Do not alter the existing upload state machine logic
    - _Requirements: 5.2, 5.3, 5.4_

  - [ ]* 6.3 Write unit tests for nav and view switching
    - Both nav options render (Requirements 5.1)
    - Selecting "My Inventory" shows dashboard and hides upload flow (Requirements 5.2)
    - Selecting "Upload" shows upload flow and hides dashboard (Requirements 5.3)
    - Initial render defaults to Upload flow (Requirements 5.4)

- [ ] 7. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend (Python) and Frontend (TypeScript) can be developed in parallel after task 1.1/2.1 and 4.1/4.2 are done
- The frontend `.env` must include `VITE_LIST_API_ENDPOINT` pointing to the deployed `/list-products` API Gateway URL
- Infrastructure (IAM least-privilege, API Gateway wiring — Requirements 6.1-6.4) is verified by template review, not automated tests

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "4.1", "4.2"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "1.5", "1.6", "4.3", "5.1", "6.1"] },
    { "id": 2, "tasks": ["5.2", "5.3", "6.2"] },
    { "id": 3, "tasks": ["6.3"] }
  ]
}
```
