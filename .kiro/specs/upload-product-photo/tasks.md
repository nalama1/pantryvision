# Implementation Plan: Upload Product Photo

## Overview

This plan implements the upload-product-photo feature using a presigned URL pattern. The React frontend handles file selection, validation, preview, and direct-to-S3 upload. An AWS Lambda function (Python 3.12 + boto3) generates presigned PUT URLs. The implementation is incremental: backend first (Lambda handler + tests), then frontend (validation, preview, upload), then infrastructure, then integration wiring.

## Tasks

- [x] 1. Set up backend Lambda function with Python 3.12
  - [x] 1.1 Create Lambda handler with request validation and presigned URL generation
    - Create `/backend/upload-product-photo/handler.py` with `lambda_handler(event, context)` function
    - Import `boto3`, `json`, `os`, `uuid`, `logging`
    - Initialize `s3_client` using `boto3.client("s3")` at module level
    - Read `BUCKET_NAME` from environment variables
    - Define constants: `ALLOWED_CONTENT_TYPES`, `MAX_CONTENT_LENGTH` (5 MB), `URL_EXPIRATION_SECONDS` (300)
    - Parse request body from `event["body"]` (handle JSON decode errors)
    - Validate required parameters: `contentType` and `fileExtension` (return 400 MISSING_PARAMS if absent)
    - Validate `contentType` against allowed set (return 400 INVALID_CONTENT_TYPE if invalid)
    - Generate unique object key using `uuid.uuid4()` in format `{uuid}.{extension}`
    - Call `s3_client.generate_presigned_url("put_object", ...)` with ContentType param and 300s expiration
    - Return `{"uploadUrl", "objectKey"}` on success with CORS headers
    - Create `_error_response(status_code, error_code, message)` helper function
    - Handle `botocore.exceptions.ClientError` → return 500 INTERNAL_ERROR
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7, 2.8, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 1.2 Write unit tests for Lambda handler with pytest and moto
    - Create `/backend/upload-product-photo/tests/__init__.py` (empty)
    - Create `/backend/upload-product-photo/tests/test_handler.py`
    - Use `moto` mock for S3 (`@mock_aws` decorator)
    - Setup: create mock S3 bucket `pantryvision-product-images` in fixture
    - Test: returns 200 with valid `uploadUrl` and `objectKey` for image/jpeg
    - Test: returns 400 with MISSING_PARAMS when `contentType` is missing
    - Test: returns 400 with MISSING_PARAMS when `fileExtension` is missing
    - Test: returns 400 with INVALID_CONTENT_TYPE for `application/pdf`
    - Test: returns 500 when boto3 raises ClientError (patch `generate_presigned_url`)
    - Test: generated `objectKey` matches UUID v4 pattern `{uuid}.{ext}`
    - Test: response includes CORS header `Access-Control-Allow-Origin`
    - Test: handles malformed JSON body gracefully (returns 400)
    - _Requirements: 2.1, 2.2, 2.3, 2.8, 4.4, 4.5_

  - [ ]* 1.3 Write property tests for Lambda handler with hypothesis
    - Create `/backend/upload-product-photo/tests/test_handler_properties.py`
    - Import `hypothesis` strategies (`st.text`, `st.sampled_from`, `st.lists`)
    - Use `moto` `@mock_aws` for S3 mocking in each property test
    - **Property 4: Presigned URL generation produces unique object keys**
      - Generate N requests (N=20) with identical contentType and fileExtension
      - Collect all objectKeys and assert all are distinct
    - **Validates: Requirements 2.2, 4.7**
    - **Property 5: Presigned URL scoped to requested content type**
      - Generate random contentType from allowed set
      - Assert the presigned URL contains the correct ContentType parameter encoding
    - **Validates: Requirements 2.4**
    - **Property 6: Backend rejects invalid content types**
      - Generate random strings NOT in {image/jpeg, image/png, image/webp}
      - Assert handler returns 400 with error code INVALID_CONTENT_TYPE
    - **Validates: Requirements 4.4, 4.5**
    - **Property 7: Backend rejects requests with missing parameters**
      - Generate request bodies with randomly omitted contentType/fileExtension fields
      - Assert handler returns 400 with error code MISSING_PARAMS
    - **Validates: Requirements 2.8**

- [x] 2. Checkpoint - Backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement frontend file validation logic
  - [x] 3.1 Create validation utility function
    - Create `/frontend/src/components/PhotoUploader/validateFile.ts`
    - Implement `validateFile(file: File): Promise<ValidationResult>`
    - Define `ValidationResult` type: `{ valid: true } | { valid: false; error: UploadError }`
    - Define `UploadError` type with codes: INVALID_TYPE, FILE_TOO_LARGE, INVALID_RESOLUTION
    - Validate MIME type against allowed set (image/jpeg, image/png, image/webp)
    - Validate file size against 5 MB maximum (5,242,880 bytes)
    - Validate image resolution (min 200×200, max 4096×4096) using `Image` element and `createObjectURL`
    - Return structured error with code and user-friendly message on failure
    - _Requirements: 1.3, 1.4, 1.5, 1.8_

  - [ ]* 3.2 Write property tests for file validation with fast-check
    - Create `/frontend/src/components/__tests__/PhotoUploader.property.test.tsx`
    - Import `fc` from `fast-check`
    - **Property 1: File type validation rejects invalid MIME types**
      - Generate random strings NOT in {image/jpeg, image/png, image/webp}
      - Assert `validateFile()` returns rejection with INVALID_TYPE error code
    - **Validates: Requirements 1.3, 1.4**
    - **Property 2: File size validation rejects oversized files**
      - Generate random integers > 5,242,880
      - Create mock File with that size and valid MIME type
      - Assert `validateFile()` returns rejection with FILE_TOO_LARGE error code
    - **Validates: Requirements 1.5**
    - **Property 3: Resolution validation rejects out-of-bounds images**
      - Generate random (width, height) pairs outside [200, 4096] range
      - Assert `validateFile()` returns rejection with INVALID_RESOLUTION error code
    - **Validates: Requirements 1.8**

  - [ ]* 3.3 Write unit tests for file validation
    - Create `/frontend/src/components/__tests__/PhotoUploader.test.tsx`
    - Test: accepts a valid JPEG file of 2 MB at 800×600
    - Test: rejects a PDF file (invalid MIME type) with INVALID_TYPE error
    - Test: rejects a 6 MB file with FILE_TOO_LARGE error
    - Test: rejects image with resolution 100×100 (below minimum)
    - Test: rejects image with resolution 5000×5000 (above maximum)
    - Test: accepts image at exact boundary dimensions (200×200 and 4096×4096)
    - _Requirements: 1.3, 1.4, 1.5, 1.8_

- [x] 4. Checkpoint - Frontend validation tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement PhotoUploader component with preview and upload
  - [x] 5.1 Create PhotoUploader component with file selection and camera support
    - Create `/frontend/src/components/PhotoUploader/PhotoUploader.tsx`
    - Define `PhotoUploaderProps` interface: `{ onUploadComplete, onError? }`
    - Define internal state: `UploadState`, `selectedFile`, `previewUrl`, `uploadProgress`, `retryCount`, `presignRetried`, `errorInfo`
    - Implement file input for gallery selection (`accept="image/jpeg,image/png,image/webp"`)
    - Implement camera capture option using `navigator.mediaDevices` availability check
    - Hide camera option if `navigator.mediaDevices` is unavailable or access denied
    - Integrate `validateFile()` on file selection — display errors if validation fails
    - Remain in idle state if user cancels file selection (no error displayed)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [x] 5.2 Implement image preview functionality
    - Show image preview using `URL.createObjectURL()` after successful validation
    - Display preview at minimum 200×200 pixels maintaining original aspect ratio
    - Render preview within 1 second of selection
    - Provide confirm button to initiate upload flow
    - Provide cancel button: revoke object URL, clear all state, return to idle
    - Handle preview render failure (`Image.onerror`) with PREVIEW_FAILED error message
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 5.3 Implement presigned URL request and S3 upload logic
    - Create `requestPresignedUrl(contentType: string, fileExtension: string): Promise<PresignedUrlResponse>`
    - Call backend `POST /upload-url` endpoint with `{ contentType, fileExtension }`
    - On success, implement `uploadToS3(file: File, presignedUrl: string): Promise<void>`
    - Upload file to S3 via HTTP PUT with `Content-Type` header matching file MIME type
    - Implement progress tracking using `XMLHttpRequest` `upload.onprogress` event
    - Display progress indicator (0-100%) during upload
    - On success (S3 returns 200): show confirmation, invoke `onUploadComplete(objectKey)`
    - Disable confirm/cancel buttons during upload
    - _Requirements: 2.1, 3.1, 3.2, 3.3, 3.7, 5.3_

  - [x] 5.4 Implement retry logic and error handling
    - Implement network error detection and retry (up to 3 attempts, exponential backoff: 1s, 2s, 4s)
    - Implement presigned URL expiration detection (S3 returns 403) with automatic URL refresh and single retry
    - If automatic presigned retry also fails, show final error and allow manual new upload
    - Implement 30-second upload timeout using `AbortController`
    - Show appropriate error messages for each failure type (network, timeout, presign expired)
    - Allow manual retry button after final failure
    - _Requirements: 3.4, 3.5, 3.6, 3.8_

  - [ ]* 5.5 Write unit tests for PhotoUploader component
    - Add tests to `/frontend/src/components/__tests__/PhotoUploader.test.tsx`
    - Test: renders idle state on initial mount (file input visible, no preview)
    - Test: renders preview state after valid file selection
    - Test: shows progress bar during upload
    - Test: cancel from preview returns to idle state (no preview, no file reference)
    - Test: camera option hidden when `navigator.mediaDevices` unavailable
    - Test: expired presigned URL (403) triggers automatic refresh and retry
    - Test: timeout at 30 seconds aborts request and shows timeout error
    - Test: displays success confirmation after upload completes
    - Test: retry button appears after network error
    - Test: max 3 retry attempts, then final error state
    - _Requirements: 1.1, 1.6, 3.2, 3.4, 3.5, 3.7, 3.8, 5.1, 5.2_

  - [ ]* 5.6 Write property tests for PhotoUploader behavior with fast-check
    - Add to `/frontend/src/components/__tests__/PhotoUploader.property.test.tsx`
    - **Property 8: Successful upload propagates correct object key**
      - Generate random valid files with mocked successful presigned URL + S3 upload
      - Assert `onUploadComplete` is called with the exact `objectKey` from presigned response
    - **Validates: Requirements 3.3**
    - **Property 9: Network error retry bounded to 3 attempts**
      - Generate random number of consecutive failures (1-5)
      - Assert retry allowed for first 3, final error state after 3rd failure
    - **Validates: Requirements 3.4**
    - **Property 10: Cancel from preview resets to initial state**
      - Generate random file selections → trigger cancel → assert state equals idle
    - **Validates: Requirements 5.2**

- [x] 6. Checkpoint - Frontend component tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. S3 bucket and infrastructure configuration
  - [x] 7.1 Configure S3 bucket with security and CORS settings
    - Create or update S3 bucket configuration in `/infra` directory
    - Enable all Block Public Access settings (BlockPublicAcls, BlockPublicPolicy, IgnorePublicAcls, RestrictPublicBuckets)
    - Configure CORS: AllowedMethods=PUT, AllowedHeaders=Content-Type, AllowedOrigins=Amplify app domain, ExposeHeaders=ETag
    - Set MaxAgeSeconds to 3600 for CORS preflight cache
    - _Requirements: 4.1, 4.8_

  - [x] 7.2 Configure Lambda function with IAM role and environment
    - Define Lambda function configuration in `/infra` directory
    - Set runtime to Python 3.12, memory to 128 MB, timeout to 10 seconds
    - Set handler to `handler.lambda_handler`
    - Create IAM execution role with minimum permissions (`s3:PutObject` on `arn:aws:s3:::pantryvision-product-images/*`)
    - Set environment variables: `BUCKET_NAME=pantryvision-product-images`
    - Configure API Gateway endpoint `POST /upload-url` with IAM authorization
    - _Requirements: 2.5, 4.2, 4.3_

- [x] 8. Integration wiring and final verification
  - [x] 8.1 Wire frontend to backend API endpoint
    - Configure API endpoint URL in frontend (environment variable or Amplify config)
    - Ensure frontend uses IAM-based authentication (AWS Signature V4 via Amplify Auth) for API calls
    - Export `PhotoUploader` component from components index
    - Verify end-to-end flow: select file → validate → preview → confirm → presign → upload → success
    - _Requirements: 2.1, 2.5, 3.1, 3.3, 4.3_

  - [ ]* 8.2 Write integration tests for backend
    - Create `/backend/upload-product-photo/tests/test_integration.py`
    - Use `moto` `@mock_aws` to simulate full S3 interaction
    - Test: request presigned URL → use URL to PUT a test file → verify object exists in mock bucket
    - Test: presigned URL with expired TTL returns 403 on upload attempt
    - Test: CORS headers present in Lambda response
    - _Requirements: 3.1, 4.1, 4.8_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend is implemented first so the API contract is stable before frontend integration
- Backend: Python 3.12 with boto3 (no framework), tested with pytest + hypothesis + moto
- Frontend: React/TypeScript, tested with Vitest + fast-check + React Testing Library
- All code and comments in English
- Python naming: snake_case for functions and variables
- TypeScript naming: camelCase for functions/variables, PascalCase for components/interfaces

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["3.1", "7.1", "7.2"] },
    { "id": 3, "tasks": ["3.2", "3.3"] },
    { "id": 4, "tasks": ["5.1"] },
    { "id": 5, "tasks": ["5.2"] },
    { "id": 6, "tasks": ["5.3"] },
    { "id": 7, "tasks": ["5.4"] },
    { "id": 8, "tasks": ["5.5", "5.6"] },
    { "id": 9, "tasks": ["8.1"] },
    { "id": 10, "tasks": ["8.2"] }
  ]
}
```
