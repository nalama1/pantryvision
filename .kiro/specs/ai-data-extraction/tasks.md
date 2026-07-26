# Implementation Plan: AI Data Extraction

## Overview

Implement the AI data extraction pipeline: a Python Lambda that retrieves product images from S3, invokes Amazon Bedrock Amazon Nova Pro for structured data extraction, and returns results to a React ReviewForm component where users confirm or edit extracted fields. Infrastructure is defined via CloudFormation. The backend and infra can be built in parallel, followed by the frontend, then wiring everything together.

## Tasks

- [x] 1. Backend Lambda: extract-product-data
  - [x] 1.1 Create handler with request validation and response helpers
    - Create `/backend/extract-product-data/handler.py` and `__init__.py`
    - Implement `lambda_handler` entry point that parses the request body
    - Implement `validate_request(body)` — checks objectKey presence and validates UUID+extension regex (`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|jpeg|png|webp)$`)
    - Implement `build_success_response(extraction)` and `build_error_response(status, code, message)` with CORS headers
    - Return 400 MISSING_PARAMS if objectKey absent, 400 INVALID_OBJECT_KEY if format invalid
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 3.4_

  - [x] 1.2 Implement S3 image retrieval
    - Implement `retrieve_image(object_key)` — calls `s3_client.get_object()` on BUCKET_NAME
    - Return image bytes and derive format from content type (jpeg/png/webp)
    - Handle `NoSuchKey` exception → return 404 IMAGE_NOT_FOUND
    - _Requirements: 1.1, 3.2_

  - [x] 1.3 Implement Bedrock invocation via Converse API
    - Implement `invoke_bedrock(image_bytes, image_format)` using `bedrock_runtime.converse()`
    - Use model ID from `BEDROCK_MODEL_ID` env var (default: `amazon.nova-pro-v1:0`)
    - Pass image + EXTRACTION_PROMPT in messages, inferenceConfig with maxTokens=1024, temperature=0
    - Set socket timeout to BEDROCK_TIMEOUT (default 30s)
    - Log model ID, duration_ms, input_tokens, output_tokens
    - Handle timeout and ClientError → return None to signal failure
    - _Requirements: 1.2, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3_

  - [x] 1.4 Implement response parsing and date normalization
    - Implement `parse_extraction(raw_response)` — parses JSON from model text output
    - Define EXTRACTION_PROMPT constant with field definitions and confidence instructions
    - Normalize expirationDate to YYYY-MM-DD format (handle various input date formats)
    - Handle malformed JSON → return all-null extraction with confidence "low"
    - Handle partial results — preserve extracted fields, set missing to null with "low" confidence
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.3_

  - [x] 1.5 Wire handler orchestration and error handling
    - Connect all functions in `lambda_handler`: validate → retrieve → invoke → parse → respond
    - On Bedrock failure (None return): respond with HTTP 200, all-null fields, confidence "low"
    - Wrap with try/except for unexpected errors → 500 INTERNAL_ERROR (log details, return generic message)
    - _Requirements: 1.3, 1.4, 3.1, 6.4, 7.4_

  - [ ]* 1.6 Write unit tests for backend handler
    - Test `validate_request` with valid/invalid object keys and missing params
    - Test `parse_extraction` with well-formed JSON, malformed JSON, partial fields, date normalization
    - Test `build_success_response` and `build_error_response` structure and CORS headers
    - Mock S3 and Bedrock calls for `lambda_handler` integration tests
    - _Requirements: 7.1, 7.2, 2.1, 2.2, 2.3, 3.1_

- [x] 2. Infrastructure: CloudFormation template
  - [x] 2.1 Create lambda-extract.yaml CloudFormation template
    - Create `/infra/lambda-extract.yaml` following the pattern from `lambda-upload.yaml`
    - Define IAM role with s3:GetObject on bucket and bedrock:Converse on `amazon.nova-pro-v1:0`
    - Define Lambda function: Python 3.12, 60s timeout, 256MB memory, handler.lambda_handler
    - Set environment variables: BUCKET_NAME, BEDROCK_MODEL_ID, BEDROCK_TIMEOUT
    - Add API Gateway REST API with POST /extract-product-data (AWS_IAM auth)
    - Add OPTIONS /extract-product-data for CORS preflight
    - Add Lambda invoke permission for API Gateway
    - Add deployment and outputs (endpoint URL, Lambda ARN, role ARN)
    - _Requirements: 1.4, 6.4, 7.3_

- [x] 3. Checkpoint - Backend and infra complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Frontend: ReviewForm component and extraction service
  - [x] 4.1 Create types and extraction service
    - Create `/frontend/src/components/ReviewForm/` directory
    - Create `types.ts` with ExtractionResult, ProductData, ReviewFormProps interfaces
    - Create `extractionService.ts` with `requestExtraction(objectKey)` function
    - Use `import.meta.env.VITE_API_ENDPOINT` for API base URL
    - Create custom `ExtractionServiceError` class for error handling
    - Create `index.ts` barrel export
    - _Requirements: 2.1, 2.4, 4.1_

  - [x] 4.2 Implement ReviewForm component
    - Create `ReviewForm.tsx` with editable inputs for productName, brand, presentation, expirationDate
    - Pre-fill inputs with extracted values (or empty if null)
    - Visually highlight fields with confidence "low" (amber border + warning indicator)
    - Validate productName is non-empty (trimmed) on submit
    - On valid submit, call `onConfirm(productData)` with current field values
    - On cancel, call `onCancel()`
    - Ensure accessibility: labels, aria attributes, keyboard navigation
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 4.3 Write unit tests for ReviewForm
    - Test rendering with full extraction, partial extraction, all-null extraction
    - Test confidence highlighting for low-confidence fields
    - Test productName validation (empty/whitespace rejected)
    - Test that submit produces correct ProductData with user-edited values
    - Test cancel callback
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 4.4 Write property tests for extraction logic
    - **Property 1: Object key validation round trip** — generate random strings, verify accept/reject matches UUID+extension regex
    - **Validates: Requirements 7.1, 7.2**
    - **Property 6: ReviewForm productName validation** — generate whitespace-only and valid strings, verify form acceptance/rejection
    - **Validates: Requirements 4.4**
    - **Property 7: ReviewForm preserves user edits** — generate ExtractionResult + random edits, verify ProductData contains edited values
    - **Validates: Requirements 4.3, 4.5**

- [x] 5. Integration: Wire upload → extract → review flow
  - [x] 5.1 Connect PhotoUploader to extraction and ReviewForm in App.tsx
    - Update `App.tsx` to manage app state: 'upload' | 'extracting' | 'review' | 'done'
    - On upload complete: transition to 'extracting', call `requestExtraction(objectKey)`
    - On extraction success: transition to 'review', pass ExtractionResult to ReviewForm
    - On extraction error: still show ReviewForm with empty fields (AI never blocks)
    - On ReviewForm confirm: transition to 'done', log/store ProductData
    - On ReviewForm cancel: transition back to 'upload'
    - Update component barrel exports to include ReviewForm
    - _Requirements: 1.1, 3.1, 4.1, 4.5_

  - [x] 5.2 Add loading state and error handling UI
    - Show a loading spinner/message during extraction (extracting state)
    - Display extraction error message with option to proceed with manual entry
    - Add "Upload another" flow from done state back to upload
    - _Requirements: 3.1, 4.1_

- [x] 6. Final checkpoint - All components integrated
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP (hackathon deadline July 27)
- Backend follows the established pattern from `/backend/upload-product-photo/handler.py`
- Infrastructure follows the pattern from `/infra/lambda-upload.yaml`
- Frontend uses the existing Vite + React + TypeScript setup with fast-check for property tests
- The VITE_API_ENDPOINT env var must be added to `.env.example` for the extract endpoint
- Bedrock model is configurable via env var — can switch to Nova Pro for better accuracy later
- AI failures return HTTP 200 with all-null fields so the ReviewForm always renders

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4"] },
    { "id": 3, "tasks": ["1.5", "4.1"] },
    { "id": 4, "tasks": ["1.6", "4.2"] },
    { "id": 5, "tasks": ["4.3", "4.4", "5.1"] },
    { "id": 6, "tasks": ["5.2"] }
  ]
}
```
