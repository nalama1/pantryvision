# Requirements Document

## Introduction

This feature enables persisting confirmed product data to a DynamoDB inventory table. After the user reviews and confirms AI-extracted (or manually entered) product data, the frontend calls a new POST /save-product endpoint. A new Lambda function validates the payload, generates a unique productId, and writes the product record to the pantryvision-products DynamoDB table. The infrastructure adds the DynamoDB table, the Lambda function, and the API Gateway route to the existing pantryvision-upload-api stack.

## Glossary

- **Save_Product_Lambda**: The AWS Lambda function (save-product) responsible for validating incoming product data and persisting it to DynamoDB.
- **Products_Table**: The Amazon DynamoDB table (pantryvision-products) that stores product inventory records in on-demand capacity mode.
- **Upload_API**: The existing API Gateway REST API (pantryvision-upload-api) that routes HTTP requests to backend Lambda functions.
- **Frontend_App**: The React single-page application that orchestrates photo upload, AI extraction, review, and product confirmation.
- **Product_Record**: A DynamoDB item containing: productId, productName, brand, presentation, expirationDate, imageKey, createdAt, quantity, unit.

## Requirements

### Requirement 1: Save Confirmed Product to Inventory

**User Story:** As a household manager, I want to save confirmed product data to my inventory, so that I can track what I have and when it expires.

#### Acceptance Criteria

1. WHEN the Frontend_App sends a POST request to /save-product with a valid payload, THE Save_Product_Lambda SHALL generate a UUID v4 productId, set createdAt to the current ISO 8601 UTC timestamp, and write the Product_Record to the Products_Table.
2. WHEN the Products_Table write succeeds, THE Save_Product_Lambda SHALL return an HTTP 200 response containing the complete Product_Record including the generated productId and createdAt.
3. WHEN the request body is missing required fields (productName, imageKey), THE Save_Product_Lambda SHALL return an HTTP 400 response with error code "MISSING_PARAMS" and a descriptive message identifying the missing fields.
4. WHEN the request body contains an imageKey that does not match the expected UUID-with-extension pattern, THE Save_Product_Lambda SHALL return an HTTP 400 response with error code "INVALID_IMAGE_KEY" and a descriptive message.
5. IF the Products_Table write fails due to a DynamoDB error, THEN THE Save_Product_Lambda SHALL return an HTTP 500 response with error code "INTERNAL_ERROR" and log the error without exposing internal details to the client.

### Requirement 2: Default Values for Optional Fields

**User Story:** As a household manager, I want the system to apply sensible defaults for quantity and unit when I do not specify them, so that I can save products without extra form fields.

#### Acceptance Criteria

1. WHEN the request body omits the quantity field, THE Save_Product_Lambda SHALL default quantity to 1 in the persisted Product_Record.
2. WHEN the request body omits the unit field, THE Save_Product_Lambda SHALL default unit to "unit" in the persisted Product_Record.
3. WHEN the request body provides a quantity value, THE Save_Product_Lambda SHALL validate that quantity is a positive integer and use the provided value.
4. IF the request body provides a quantity that is not a positive integer, THEN THE Save_Product_Lambda SHALL return an HTTP 400 response with error code "INVALID_QUANTITY" and a descriptive message.

### Requirement 3: Frontend Passes Image Key and Calls Save Endpoint

**User Story:** As a household manager, I want the confirm action to automatically save my product to the inventory, so that I do not have to perform an additional step after reviewing data.

#### Acceptance Criteria

1. WHEN the user confirms product data in the ReviewForm, THE Frontend_App SHALL send a POST request to the /save-product endpoint including productName, brand, presentation, expirationDate, and the imageKey (objectKey from the upload step).
2. WHILE the save request is in progress, THE Frontend_App SHALL display a loading indicator to inform the user the operation is pending.
3. WHEN the /save-product endpoint returns HTTP 200, THE Frontend_App SHALL transition to the "done" state and display the saved product name.
4. IF the /save-product endpoint returns an error response, THEN THE Frontend_App SHALL display an error message to the user and remain on the review screen so the user can retry.

### Requirement 4: DynamoDB Table Infrastructure

**User Story:** As a developer, I want the DynamoDB table defined as infrastructure-as-code, so that it can be provisioned consistently across environments.

#### Acceptance Criteria

1. THE Products_Table SHALL use on-demand (PAY_PER_REQUEST) billing mode.
2. THE Products_Table SHALL use productId (String type) as the partition key.
3. THE Products_Table SHALL have server-side encryption enabled with AWS-owned keys (SSE with default encryption).
4. THE Products_Table SHALL be defined in a CloudFormation template stored in the /infra directory.

### Requirement 5: API Gateway Route for Save Product

**User Story:** As a developer, I want the /save-product route added to the existing API Gateway, so that it shares the same base URL as other PantryVision endpoints.

#### Acceptance Criteria

1. THE Upload_API SHALL expose a POST method on the /save-product resource path that integrates with the Save_Product_Lambda using AWS_PROXY integration.
2. THE Upload_API SHALL expose an OPTIONS method on the /save-product resource path that returns CORS preflight headers allowing POST requests from any origin.
3. WHEN the Save_Product_Lambda is invoked via API Gateway, THE Save_Product_Lambda SHALL include CORS headers (Access-Control-Allow-Origin: *) in every response.

### Requirement 6: Lambda Execution Role Permissions

**User Story:** As a developer, I want the save-product Lambda to have only the minimum required permissions, so that the system follows the principle of least privilege.

#### Acceptance Criteria

1. THE Save_Product_Lambda execution role SHALL have permission to write items (dynamodb:PutItem) to the Products_Table only.
2. THE Save_Product_Lambda execution role SHALL have the AWSLambdaBasicExecutionRole managed policy for CloudWatch Logs access.
3. THE Save_Product_Lambda execution role SHALL have no permissions beyond those specified in criteria 1 and 2.

## Future Considerations

The current schema uses generic quantity/unit fields as an MVP simplification. A future iteration should replace these with a pack/unit distinction (e.g., stockPacks, unitsPerPack, totalUnits) to match the original product requirement of tracking purchases like "1 pack of 3 units" — this was deferred to keep the ReviewForm simple for the hackathon MVP, and should be addressed when building the inventory management view.
