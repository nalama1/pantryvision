# Implementation Plan: Expiration Alerts

## Overview

Implement the `check-expiring-products` Lambda function (Python 3.12) that is triggered daily by an Amazon EventBridge rule, scans the `pantryvision-products` DynamoDB table, classifies products as `Expiring_Product` or `Expired_Product`, and sends a single consolidated Amazon SES email when needed. Work proceeds bottom-up: pure functions (`classify_products`, `build_email_body`) and their property tests first, then I/O functions (`scan_products`, `send_alert_email`, `get_alert_config`, `log_run_summary`) with their tests, then the orchestrating `lambda_handler`, then the integration tests, then the CloudFormation infrastructure template, and finally the manual SES verification and deployment steps.

## Tasks

- [x] 1. Set up Lambda project structure and shared types
  - Create `backend/check-expiring-products/` directory with `handler.py` and `__init__.py`, following the same layout as `backend/list-products/`
  - Create `backend/check-expiring-products/requirements.txt` listing `hypothesis` and `moto` as test dependencies (boto3 is provided by the Lambda runtime)
  - In `handler.py`, define the `AlertConfig`, `ClassifiedProduct`, `AlertBatch`, and `DeliveryResult` `TypedDict`/type-alias definitions from the design's Data Models section, plus module-level constants (`TABLE_NAME` default, `EXPIRING_WINDOW_DAYS = 7`) and the module-level `logger`
  - _Requirements: 4.2_

- [x] 2. Implement classification and email body construction (pure functions)
  - [x] 2.1 Implement `classify_products(products, current_date)`
    - Pure function classifying each product record by comparing `expirationDate` to `current_date`: `Expiring_Product` when `0 <= (expirationDate - current_date).days <= 7`, `Expired_Product` when `expirationDate < current_date`, excluded when `expirationDate` is missing/absent
    - Returns an `AlertBatch` of `ClassifiedProduct` entries (product_name, expiration_date, classification)
    - _Requirements: 1.2, 1.3, 1.4, 1.5_

  - [ ]* 2.2 Write property test for classification by day offset
    - **Property 1: Classification correctness by day offset**
    - **Validates: Requirements 1.3, 1.4**
    - Use `hypothesis` to generate a current date and integer offset N; assert classification matches `Expiring_Product` iff `0 <= N <= 7` and `Expired_Product` iff `N < 0`

  - [ ]* 2.3 Write property test for missing expirationDate exclusion
    - **Property 2: Products without expirationDate are always excluded**
    - **Validates: Requirements 1.5**
    - Use `hypothesis` to generate mixed lists of product records with/without `expirationDate`; assert records missing the attribute never appear in the resulting batch and all others classify correctly

  - [ ]* 2.4 Write property test for classification statelessness
    - **Property 7: Classification is stateless across runs**
    - **Validates: Requirements 2.5**
    - Use `hypothesis` to generate a fixed product list and current date; assert calling `classify_products` twice produces identical results

  - [x] 2.5 Implement `build_email_body(alert_batch)`
    - Pure function returning `(subject, body)` text listing product name, expiration date, and classification for every entry
    - _Requirements: 2.3_

  - [ ]* 2.6 Write property test for non-empty batch email completeness
    - **Property 6: Non-empty batch produces exactly one complete email**
    - **Validates: Requirements 2.2, 2.3**
    - Use `hypothesis` to generate non-empty alert batches; assert the built body contains the product name, expiration date, and classification label for every entry (send-once assertion covered together with `send_alert_email` in task 4.3)

  - [ ]* 2.7 Write unit tests for classify_products and build_email_body edge cases
    - Cover boundary offsets (exactly 0 and exactly 7 days), empty product list, and empty alert batch producing an empty body
    - _Requirements: 1.3, 1.4, 1.5, 2.3, 2.4_

- [x] 3. Checkpoint - Ensure all classification/email-body tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement configuration reading, DynamoDB scan, and SES send (I/O functions)
  - [x] 4.1 Implement `get_alert_config()`
    - Reads `ALERT_SENDER_EMAIL`, `ALERT_RECIPIENT_EMAIL`, and `TABLE_NAME` from environment variables; raises `ConfigurationError` naming the missing variable when sender or recipient is missing/blank, without ever hardcoding email addresses
    - _Requirements: 2.8, 3.2, 4.2_

  - [ ]* 4.2 Write unit tests for get_alert_config
    - Cover missing sender only, missing recipient only, both missing, both present, and blank-string values
    - _Requirements: 2.8_

  - [x] 4.3 Implement `scan_products(table)`
    - Scans the full table across pages via `LastEvaluatedKey`; on transient `ClientError`, retries up to 3 total attempts with a short backoff; raises `ScanFailedError` after exhausting retries
    - _Requirements: 1.1, 1.6_

  - [ ]* 4.4 Write property test for full pagination coverage
    - **Property 3: Full pagination coverage**
    - **Validates: Requirements 1.1**
    - Use `hypothesis` with mocked DynamoDB scan responses split across an arbitrary number of pages; assert `scan_products` returns the exact concatenation of all items regardless of distribution

  - [ ]* 4.5 Write property test for DynamoDB scan retry bound
    - **Property 4: DynamoDB scan retry bound**
    - **Validates: Requirements 1.6, 2.6**
    - Use `hypothesis` to inject sequences of transient DynamoDB errors; assert `scan_products` attempts the scan at most 3 times total before raising `ScanFailedError`

  - [x] 4.6 Implement `send_alert_email(ses_client, sender, recipient, subject, body)`
    - Sends via `ses_client.send_email`; classifies `ClientError` codes as transient (e.g., `Throttling`, `ServiceUnavailable`) or non-transient (e.g., `MessageRejected`, `MailFromDomainNotVerified`); retries transient failures up to 2 additional times (3 total) with a minimum 2-second delay between attempts; does not retry non-transient failures; returns a `DeliveryResult`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 4.7 Write property test for SES retry bound and backoff
    - **Property 8: SES retry bound and backoff for transient failures**
    - **Validates: Requirements 2.7, 3.3**
    - Use `hypothesis` to inject sequences of transient SES errors; assert at most 3 total attempts, at least 2 seconds between consecutive attempts (mock `time.sleep`), and a `failed` result only after exhausting attempts

  - [ ]* 4.8 Write property test for non-transient SES failures
    - **Property 9: Non-transient SES failures never retry**
    - **Validates: Requirements 3.4**
    - Use `hypothesis` to inject non-transient SES error codes; assert exactly one send attempt and an immediate `failed` `DeliveryResult`

  - [ ]* 4.9 Write property test for empty batch never sending email
    - **Property 5: Empty batch never triggers an email**
    - **Validates: Requirements 2.4**
    - Use `hypothesis` to generate product lists where every record is excluded or outside the alert window; assert the resulting batch is empty and `send_alert_email` is never invoked (test at the orchestration level using a mock send function)

  - [x] 4.10 Implement `log_run_summary(expiring_count, expired_count, status, failure_reason=None)`
    - Logs a single structured summary line to CloudWatch containing only counts, status, and failure reason (never email addresses, image keys, or raw product data)
    - _Requirements: 5.1, 5.2, 5.4_

  - [ ]* 4.11 Write property test for run summary log accuracy
    - **Property 11: Run summary log reflects actual outcome**
    - **Validates: Requirements 5.1, 5.2**
    - Use `hypothesis` to generate product sets and mocked SES outcomes; assert logged `expiring_count`/`expired_count` match the actual batch composition and `status`/`failure_reason` match what happened

  - [ ]* 4.12 Write property test for sensitive-value log leakage
    - **Property 12: No log entry ever leaks sensitive values**
    - **Validates: Requirements 2.6, 3.5, 4.5, 5.4**
    - Use `hypothesis` to generate product data, sender/recipient addresses, image keys, and credential-like strings (e.g., `AKIA...`); capture all logger calls throughout the pipeline and assert none contain these sensitive substrings

- [x] 5. Checkpoint - Ensure all I/O function tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement the orchestrating lambda_handler
  - [x] 6.1 Implement `lambda_handler(event, context)`
    - Orchestrates: validate config (abort + log on `ConfigurationError` before any DynamoDB call) → `scan_products` (abort + log on `ScanFailedError`, no email sent) → `classify_products` → if batch non-empty, `build_email_body` + `send_alert_email` (else skip send, status `not-needed`) → `log_run_summary`; wraps the full pipeline in a top-level `try/except Exception` that logs via `logger.exception` and terminates without a partial or duplicate email
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 3.1, 4.4, 5.1, 5.2, 5.3_

  - [ ]* 6.2 Write property test for access-denied clean termination
    - **Property 10: Access-denied failures terminate cleanly without partial output**
    - **Validates: Requirements 4.5, 5.3**
    - Use `hypothesis` to inject `AccessDenied`-style `ClientError`s from either the scan or send call; assert no Alert_Email is sent, no unhandled exception escapes `lambda_handler`, and a failure is logged

  - [ ]* 6.3 Write unit test verifying no Bedrock invocation
    - Static/behavioral check asserting no Bedrock client is created or called anywhere in `handler.py` (satisfies the no-AI requirement without needing mocked AWS infra)
    - _Requirements: 4.4_

  - [ ]* 6.4 Write integration tests for lambda_handler using moto-mocked DynamoDB and SES
    - Cover representative scenarios: empty inventory (no email), mixed inventory (email sent with correct content), DynamoDB scan failure (no email, failure logged), SES send failure (failure logged, no crash)
    - _Requirements: 1.1, 2.2, 2.4, 2.6, 2.7, 5.1, 5.3_

  - [ ]* 6.5 Write performance/integration test for 10,000-record scan within 60 seconds
    - Generate a 10,000-item mocked dataset and mocked AWS clients; assert `lambda_handler` (or the scan+classify portion) completes within 60 seconds wall-clock
    - _Requirements: 4.3_

- [x] 7. Checkpoint - Ensure all handler and integration tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Create CloudFormation infrastructure template
  - [x] 8.1 Create `infra/lambda-check-expiring.yaml`
    - Following the pattern of `infra/lambda-list-products.yaml`: define the `CheckExpiringProductsFunction` (`AWS::Lambda::Function`, runtime `python3.12`, handler `handler.lambda_handler`, env vars `TABLE_NAME`, `ALERT_SENDER_EMAIL`, `ALERT_RECIPIENT_EMAIL` sourced from template Parameters, no hardcoded values)
    - Define a least-privilege `AWS::IAM::Role` granting only `dynamodb:Scan` on the `pantryvision-products` table ARN and `ses:SendEmail`/`ses:SendRawEmail` scoped to the sender identity ARN, plus the basic Lambda execution managed policy for CloudWatch Logs
    - Define an `AWS::Events::Rule` (Daily_Schedule) with a daily cron schedule expression (UTC) targeting the Lambda function
    - Define an `AWS::Lambda::Permission` granting `events.amazonaws.com` permission to invoke the function, scoped via `SourceArn` to the EventBridge rule ARN
    - Add Outputs for the Lambda function ARN, execution role ARN, and EventBridge rule ARN
    - _Requirements: 4.1, 4.2_

  - [ ]* 8.2 Write a template-review unit test for IAM least privilege
    - Parse `infra/lambda-check-expiring.yaml` and assert the IAM policy statements reference only `dynamodb:Scan` scoped to the table ARN and `ses:SendEmail`/`ses:SendRawEmail` scoped to the sender identity, with no wildcard resources and no hardcoded secrets/emails in the template
    - _Requirements: 4.1, 4.2_

- [x] 9. Checkpoint - Ensure all tests pass before deployment steps
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Manual step: verify SES identities (sandbox mode)
  - Manually verify the Sender_Address (`ALERT_SENDER_EMAIL`) and Recipient_Address (`ALERT_RECIPIENT_EMAIL`) as verified identities in the Amazon SES console for the target region, since SES is operating in sandbox mode
  - This is a manual, non-code, deployment-prerequisite step and must be completed before deploying the stack in task 11
  - _Requirements: 3.6_

- [x] 11. Manual step: deploy the CloudFormation stack and confirm the schedule fires
  - Deploy `infra/lambda-check-expiring.yaml` (e.g., via `aws cloudformation deploy`) with the `TableName`, sender, and recipient parameters set, then confirm via CloudWatch Logs that the EventBridge rule invokes the Lambda function on its schedule and that a run summary log entry is produced
  - This is a manual deployment/verification step, not an automated test
  - _Requirements: 1.1, 5.1_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery; they are not implemented as part of the core task execution.
- Each task references specific requirement clauses for traceability back to `requirements.md`.
- Checkpoints ensure incremental validation before moving to the next layer (pure functions → I/O functions → orchestration → infrastructure → deployment).
- Property tests (Properties 1-12) validate the universal correctness properties defined in `design.md` using `hypothesis`, each run with at least 100 examples.
- Unit and integration tests use `moto` to mock DynamoDB and SES so no real AWS calls or costs are incurred during testing.
- Tasks 10 and 11 are manual/deployment steps flagged as such; they involve AWS console/CLI actions rather than code changes and are not executed by a coding agent.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "2.5", "4.1", "4.10"] },
    { "id": 1, "tasks": ["2.2", "2.3", "2.4", "2.6", "2.7", "4.2", "4.11", "4.12"] },
    { "id": 2, "tasks": ["4.3", "4.6"] },
    { "id": 3, "tasks": ["4.4", "4.5", "4.7", "4.8", "4.9"] },
    { "id": 4, "tasks": ["6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.4", "6.5"] },
    { "id": 6, "tasks": ["8.1"] },
    { "id": 7, "tasks": ["8.2"] }
  ]
}
```
