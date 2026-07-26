# Implementation Plan: Save Product to Inventory

## Overview

Implement the save-product endpoint: a DynamoDB table for product storage, a Lambda function that validates and persists product records, API Gateway routing, and frontend wiring to call the endpoint on confirm. Backend is Python 3.12, frontend is React/TypeScript, infrastructure is CloudFormation.

## Tasks

- [ ] 1. Backend handler and DynamoDB infrastructure
  - [ ] 1.1 Create the save-product Lambda handler (`/backend/save-product/handler.py`)
    - Implement `lambda_handler` that parses JSON body, calls validate, builds record, writes to DynamoDB via `boto3`, returns response
    - Implement `validate_request`: check productName (required, non-empty after trim), imageKey (required, matches UUID-extension regex), quantity (positive int if provided)
    - Implement `build_product_record`: generate UUID v4 productId, ISO 8601 UTC createdAt, default quantity=1, default unit="unit", default brand/presentation/expirationDate=""
    - Implement `build_success_response` and `build_error_response` with CORS headers (`Access-Control-Allow-Origin: *`)
    - Read table name from `TABLE_NAME` environment variable
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 5.3_

  - [ ] 1.2 Create DynamoDB CloudFormation template (`/infra/dynamodb-products.yaml`)
    - Define `pantryvision-products` table with `productId` (S) as partition key
    - BillingMode: PAY_PER_REQUEST
    - SSESpecification: SSEEnabled true
    - Export TableName and TableArn as outputs
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 2. Lambda infrastructure stack
  - [ ] 2.1 Create Lambda CloudFormation template (`/infra/lambda-save-product.yaml`)
    - Follow existing `lambda-extract.yaml` pattern
    - IAM Role: AWSLambdaBasicExecutionRole managed policy + inline policy for `dynamodb:PutItem` on products table ARN only
    - Lambda function: Python 3.12, 128MB, 10s timeout, TABLE_NAME env var
    - API Gateway REST API with POST /save-product (AWS_PROXY integration) and OPTIONS /save-product (CORS mock integration)
    - Lambda permission for API Gateway invoke
    - Deployment to prod stage
    - _Requirements: 5.1, 5.2, 6.1, 6.2, 6.3_

- [ ] 3. Checkpoint - Verify backend
  - Ensure all backend code and infrastructure templates are complete, ask the user if questions arise.

- [ ] 4. Frontend service and wiring
  - [ ] 4.1 Create product service (`/frontend/src/services/productService.ts`)
    - Define `SaveProductRequest`, `SaveProductResponse` interfaces and `SaveProductError` class
    - Implement `saveProduct()` function: POST to `VITE_SAVE_API_ENDPOINT`, handle success/error, throw `SaveProductError` on failure
    - Follow the same pattern as `extractionService.ts`
    - _Requirements: 3.1_

  - [ ] 4.2 Update App.tsx to store objectKey and wire save flow
    - Add `objectKey` state variable, store it from `handleUploadComplete`
    - Add `saving` and `saveError` state variables
    - Update `handleConfirm`: call `saveProduct()` with product data + objectKey, show loading indicator while saving, transition to "done" on success, display error and stay on review on failure
    - Pass objectKey availability through to confirm handler
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 5. Checkpoint - Verify frontend
  - Ensure all frontend code compiles and integrates correctly, ask the user if questions arise.

- [ ]*  5.1 Write property tests for save-product Lambda
    - **Property 1: Valid payload round-trip preservation** — verify all input fields preserved, UUID productId and ISO createdAt generated
    - **Property 2: Default values applied** — omitted quantity defaults to 1, omitted unit defaults to "unit"
    - **Property 3: Missing required fields rejected** — missing productName/imageKey returns 400 MISSING_PARAMS
    - **Property 4: Invalid imageKey rejected** — non-UUID-extension imageKey returns 400 INVALID_IMAGE_KEY
    - **Property 5: Invalid quantity rejected** — non-positive-integer quantity returns 400 INVALID_QUANTITY
    - **Property 6: CORS headers present** — every response includes Access-Control-Allow-Origin: *
    - **Validates: Requirements 1.1-1.5, 2.1-2.4, 5.3**

- [ ] 6. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend (Python) and Frontend (TypeScript) can be developed in parallel after wave 0
- The Lambda handler uses the same structure as the existing extract-product-data handler
- Infrastructure templates follow existing patterns in `/infra`
- The frontend `.env` must include `VITE_SAVE_API_ENDPOINT` pointing to the deployed API Gateway URL

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "4.1"] },
    { "id": 2, "tasks": ["4.2"] },
    { "id": 3, "tasks": ["5.1"] }
  ]
}
```
