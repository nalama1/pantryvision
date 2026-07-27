# Requirements Document

## Introduction

PantryVision stores household products with an `expirationDate` attribute in the `pantryvision-products` DynamoDB table. Today, users have no way to know a product is about to expire or has already expired unless they manually check the inventory. This feature adds a daily automated check that scans the inventory, identifies products expiring soon or already expired, and sends a single consolidated email alert to the household owner via Amazon SES. The check runs on a daily Amazon EventBridge schedule and invokes a dedicated AWS Lambda function. No AI processing is involved in this feature, and no per-user accounts or notification preferences are introduced, consistent with the MVP scope of the hackathon project.

## Glossary

- **Expiration_Checker**: The AWS Lambda function (Python 3.12) responsible for scanning the Products_Table, identifying Expiring_Products and Expired_Products, and requesting the Alert_Email be sent.
- **Products_Table**: The Amazon DynamoDB table `pantryvision-products` that stores product records, including the `expirationDate` attribute.
- **Expiring_Product**: A product record whose `expirationDate` falls on or between the Current_Date and the Current_Date plus 7 calendar days, inclusive.
- **Expired_Product**: A product record whose `expirationDate` is earlier than the Current_Date.
- **Alert_Batch**: The complete set of Expiring_Products and Expired_Products identified by the Expiration_Checker during a single scheduled run.
- **Alert_Email**: The single email message sent via Amazon SES that lists every product in the Alert_Batch for a given run.
- **Recipient_Address**: The fixed destination email address for the Alert_Email, configured via the `ALERT_RECIPIENT_EMAIL` environment variable.
- **Sender_Address**: The SES-verified email address used as the "From" address for the Alert_Email, configured via the `ALERT_SENDER_EMAIL` environment variable.
- **Current_Date**: The date on which the Expiration_Checker executes, in UTC.
- **Daily_Schedule**: The Amazon EventBridge rule that triggers the Expiration_Checker once every 24 hours.

## Requirements

### Requirement 1: Scheduled Scan of Products

**User Story:** As a household inventory owner, I want the system to automatically scan my inventory every day, so that I do not need to manually check which products are expiring or expired.

#### Acceptance Criteria

1. WHEN the Daily_Schedule triggers, THE Expiration_Checker SHALL retrieve every product record from the Products_Table, including records spanning multiple result pages if the table's response is paginated.
2. WHILE scanning the Products_Table, THE Expiration_Checker SHALL evaluate each product record's `expirationDate` attribute against the Current_Date, where Current_Date is the calendar date in UTC at the moment the Daily_Schedule triggers.
3. WHEN a product record's `expirationDate` falls on or between the Current_Date and the Current_Date plus 7 calendar days, THE Expiration_Checker SHALL classify the product record as an Expiring_Product and add it to the Alert_Batch.
4. WHEN a product record's `expirationDate` is earlier than the Current_Date, THE Expiration_Checker SHALL classify the product record as an Expired_Product and add it to the Alert_Batch.
5. IF a product record has no `expirationDate` attribute, THEN THE Expiration_Checker SHALL exclude the product record from the Alert_Batch and continue processing the remaining product records.
6. IF the retrieval of product records from the Products_Table fails after 3 retry attempts, THEN THE Expiration_Checker SHALL abort the current Daily_Schedule run without sending any alerts and SHALL preserve the Products_Table unchanged.

### Requirement 2: Consolidated Alert Batch

**User Story:** As a household inventory owner, I want to receive one email per day summarizing all expiring and expired products, so that I am not overwhelmed by multiple separate notifications.

#### Acceptance Criteria

1. WHEN the Expiration_Checker completes scanning the Products_Table, THE Expiration_Checker SHALL group all identified Expiring_Products and Expired_Products into a single Alert_Batch.
2. IF the Alert_Batch contains at least one product record, THEN THE Expiration_Checker SHALL send exactly one Alert_Email, via Amazon SES, containing every product record in the Alert_Batch, within 5 minutes of the Daily_Schedule trigger.
3. THE Alert_Email SHALL list, for each product record in the Alert_Batch, the product name, expiration date, and classification as Expiring_Product or Expired_Product.
4. IF the Alert_Batch contains zero product records, THEN THE Expiration_Checker SHALL send no Alert_Email for that run.
5. THE Expiration_Checker SHALL re-evaluate the full Products_Table on each Daily_Schedule trigger, including product records that were included in a previous Alert_Batch.
6. IF the Expiration_Checker fails to complete scanning the Products_Table due to an error, THEN THE Expiration_Checker SHALL send no Alert_Email for that run and SHALL record the failure in Amazon CloudWatch logs without including product data or personal information.
7. IF Amazon SES fails to send the Alert_Email after 3 attempts, THEN THE Expiration_Checker SHALL record the failure in Amazon CloudWatch logs without including product data or personal information, and SHALL NOT retry beyond the current Daily_Schedule trigger.
8. IF the Recipient_Address or Sender_Address environment variable is not configured, THEN THE Expiration_Checker SHALL abort the run before attempting to scan the Products_Table and SHALL log the misconfiguration to Amazon CloudWatch.

### Requirement 3: Email Delivery via Amazon SES

**User Story:** As a household inventory owner, I want alert emails delivered reliably to my own inbox, so that I can trust the notification system during the hackathon demo.

#### Acceptance Criteria

1. WHEN the Expiration_Checker determines the Alert_Batch contains at least one product record, THE Expiration_Checker SHALL send the Alert_Email using Amazon SES, with the Sender_Address as the "From" address and the Recipient_Address as the "To" address.
2. THE Expiration_Checker SHALL read the Sender_Address and Recipient_Address from environment variables rather than hardcoded values.
3. IF Amazon SES returns a transient failure (e.g., throttling or a 5xx service error) when sending the Alert_Email, THEN THE Expiration_Checker SHALL retry the send operation up to 2 additional times, with a minimum delay of 2 seconds between attempts, before treating the run as failed.
4. IF Amazon SES returns a non-transient failure (e.g., an unverified Sender_Address or Recipient_Address, or a malformed request) when sending the Alert_Email, THEN THE Expiration_Checker SHALL NOT retry the send operation and SHALL treat the run as failed immediately.
5. IF the Alert_Email fails to send after all applicable retries, THEN THE Expiration_Checker SHALL log the failure details to Amazon CloudWatch without including personal data beyond product names already stored in the Products_Table.
6. BEFORE the Expiration_Checker is deployed for use, THE Sender_Address and Recipient_Address SHALL both be manually verified as identities in Amazon SES, given Amazon SES is operating in sandbox mode.

### Requirement 4: Secure and Cost-Efficient Operation

**User Story:** As the project owner, I want the expiration check to run securely and at minimal cost, so that the feature aligns with the project's serverless and security principles.

#### Acceptance Criteria

1. THE Expiration_Checker SHALL use an IAM role granted only `dynamodb:Scan` (or `dynamodb:Query`) on the Products_Table and `ses:SendEmail` scoped to the Sender_Address identity.
2. THE Expiration_Checker SHALL NOT contain hardcoded AWS credentials, API keys, or email addresses in source code; the Sender_Address and Recipient_Address SHALL be sourced exclusively from environment variables.
3. THE Expiration_Checker SHALL perform a full table scan of the Products_Table on each run without requiring a new DynamoDB secondary index, for inventories of up to 10,000 product records, completing the scan and classification within 60 seconds.
4. THE Expiration_Checker SHALL complete execution without invoking Amazon Bedrock or any AI service.
5. IF the Expiration_Checker's IAM role lacks sufficient permissions to scan the Products_Table or send via Amazon SES, THEN THE Expiration_Checker SHALL log the permission failure to Amazon CloudWatch, excluding any credential values, and SHALL terminate the run without partial output.

### Requirement 5: Observability

**User Story:** As the project owner, I want visibility into whether the daily check ran successfully, so that I can troubleshoot issues during the hackathon demo.

#### Acceptance Criteria

1. WHEN the Expiration_Checker completes a run without an unhandled error, THE Expiration_Checker SHALL log the count of Expiring_Products, the count of Expired_Products, and the Alert_Email delivery status (sent, not-needed, or failed) to Amazon CloudWatch.
2. THE Expiration_Checker SHALL determine the Alert_Email delivery status as "sent" only upon receiving a successful response from Amazon SES, and SHALL log the specific failure reason returned by Amazon SES WHEN the delivery status is "failed".
3. IF an unhandled error occurs during the scan or send process, THEN THE Expiration_Checker SHALL log the error to Amazon CloudWatch and terminate the run without sending a partial or duplicate Alert_Email.
4. THE Expiration_Checker SHALL NOT include product images, personally identifiable information beyond product names already stored in the Products_Table, or AWS credentials in any Amazon CloudWatch log entry.
