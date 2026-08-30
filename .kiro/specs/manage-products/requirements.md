# Requirements Document

## Introduction

This feature completes CRUD support for PantryVision by adding Update and Delete
capabilities for products already saved in the inventory. Today the system
supports Create (upload-product-photo → extract-product-data → save-product) and
Read (list-products). This feature introduces two new backend Lambdas —
`update-product` and `delete-product` — exposed through the existing API Gateway
(pantryvision-upload-api) under the same AWS_IAM authorization model, plus
frontend controls on each product card in the Inventory_Dashboard.

Update lets the user edit the text and date fields of an existing product
(productName, brand, presentation, expirationDate) while preserving the product's
identity (productId) and its image (imageKey). Delete marks the product as
logically deleted: the product is hidden from the inventory, but the record and
its image are preserved, so an accidental deletion can be recovered and no data
is destroyed. Delete is guarded by a confirmation step in the UI to avoid
accidental removal. Changing a product's photo is explicitly out of scope and is
noted as a possible future feature.

## Glossary

- **Update_Product_Lambda**: The AWS Lambda function (`update-product`) responsible for validating an edit payload and updating an existing Product_Record in the Products_Table.
- **Delete_Product_Lambda**: The AWS Lambda function (`delete-product`) responsible for marking a Product_Record as logically deleted in the Products_Table (setting the Deletion_Attributes) rather than removing the Product_Record or its Product_Image.
- **Products_Table**: The existing Amazon DynamoDB table (`pantryvision-products`) storing product inventory records, with productId (String) as the partition key.
- **Product_Images_Bucket**: The existing private Amazon S3 bucket (`pantryvision-product-images`) storing uploaded product photos.
- **Product_Image**: The S3 object stored in the Product_Images_Bucket, identified by a Product_Record's imageKey.
- **Upload_API**: The existing API Gateway REST API (`pantryvision-upload-api`) that routes HTTP requests to backend Lambda functions using AWS_IAM authorization.
- **Frontend_App**: The React single-page application that orchestrates the Upload flow and the Inventory_Dashboard.
- **Inventory_Dashboard**: The React component that renders saved products as cards and hosts the Edit and Delete controls on each card.
- **Edit_Form**: The React form (reusing the existing ReviewForm component pattern) that is pre-filled with a product's current editable values and submits the update.
- **Delete_Confirmation**: The confirmation prompt the Frontend_App displays before sending a delete request, requiring an explicit user action to proceed.
- **Soft_Delete**: Marking a Product_Record as deleted by setting a `deleted` attribute to true and a `deletedAt` ISO 8601 timestamp, so the record is preserved in the Products_Table but excluded from normal inventory listings.
- **Deletion_Attributes**: The Product_Record attributes that record a logical deletion: `deleted` (boolean) and `deletedAt` (ISO 8601 timestamp string).
- **Editable_Fields**: The set of Product_Record fields the user may change through this feature: productName, brand, presentation, expirationDate.
- **Immutable_Fields**: The set of Product_Record fields this feature MUST preserve unchanged: productId and imageKey.
- **Product_Record**: A DynamoDB item containing: productId, productName, brand, presentation, expirationDate, imageKey, createdAt, quantity, unit. A Product_Record may also contain the optional Deletion_Attributes (`deleted`, `deletedAt`).

## Requirements

### Requirement 1: Update an Existing Product's Editable Fields

**User Story:** As a household manager, I want to edit the details of a product already in my inventory, so that I can correct AI-extraction mistakes or reflect changes without re-adding the product.

#### Acceptance Criteria

1. WHEN the Frontend_App sends a request to the /update-product endpoint with a payload where productId is a non-empty string, productName is 1-200 characters after trimming whitespace, brand is 0-100 characters, presentation is 0-100 characters, and expirationDate is either empty or matches "YYYY-MM-DD", THE Update_Product_Lambda SHALL update the matching Product_Record in the Products_Table with the provided productName, brand, presentation, and expirationDate values.
2. WHEN the Products_Table update succeeds, THE Update_Product_Lambda SHALL return an HTTP 200 response containing the complete updated Product_Record.
3. THE Update_Product_Lambda SHALL preserve the Immutable_Fields (productId and imageKey) of the Product_Record unchanged during an update.
4. THE Update_Product_Lambda SHALL preserve the createdAt, quantity, and unit fields of the Product_Record unchanged when the update payload does not include them.
5. IF the update payload omits productId or provides an empty productId, THEN THE Update_Product_Lambda SHALL return an HTTP 400 response with error code "MISSING_PARAMS" and a descriptive message identifying the missing field, without modifying any Product_Record.
6. IF the update payload omits productName or provides a productName that is empty after trimming whitespace, THEN THE Update_Product_Lambda SHALL return an HTTP 400 response with error code "MISSING_PARAMS" and a descriptive message identifying the missing field, without modifying any Product_Record.
7. IF the update payload provides a non-empty expirationDate that does not match the ISO date format "YYYY-MM-DD", THEN THE Update_Product_Lambda SHALL return an HTTP 400 response with error code "INVALID_DATE" and a descriptive message, without modifying any Product_Record.
8. IF no Product_Record in the Products_Table has a productId equal to the requested productId, THEN THE Update_Product_Lambda SHALL return an HTTP 404 response with error code "NOT_FOUND" and a descriptive message.
9. IF the request body is not valid JSON, THEN THE Update_Product_Lambda SHALL return an HTTP 400 response with error code "INVALID_JSON" and a descriptive message.
10. IF the Products_Table update fails due to a DynamoDB error, THEN THE Update_Product_Lambda SHALL return an HTTP 500 response with error code "INTERNAL_ERROR" and log the error without exposing internal details to the client.
11. IF the update payload provides a productName longer than 200 characters after trimming, or a brand longer than 100 characters, or a presentation longer than 100 characters, THEN THE Update_Product_Lambda SHALL return an HTTP 400 response with error code "INVALID_PARAMS" and a descriptive message identifying the field that exceeded its length limit, without modifying any Product_Record.

### Requirement 2: Soft-Delete a Product

**User Story:** As a household manager, I want removing a product to hide it from my inventory without permanently destroying the record, so that an accidental deletion can be recovered and no data is lost.

#### Acceptance Criteria

1. WHEN the Frontend_App sends a request to the /delete-product endpoint with a productId that is a non-empty string between 1 and 256 characters, THE Delete_Product_Lambda SHALL set the `deleted` attribute of the matching Product_Record to true and set its `deletedAt` attribute to the current UTC timestamp in ISO 8601 format, using a DynamoDB update (not a delete).
2. THE Delete_Product_Lambda SHALL preserve all other attributes of the Product_Record unchanged, including productId, imageKey, productName, brand, presentation, expirationDate, createdAt, quantity, and unit.
3. THE Delete_Product_Lambda SHALL NOT delete the associated Product_Image from the Product_Images_Bucket; the image is preserved so the soft-deleted record can be fully restored in a future feature.
4. WHEN the soft delete completes successfully, THE Delete_Product_Lambda SHALL return, within 5 seconds of receiving the request, an HTTP 200 response containing the productId of the deleted product.
5. IF the delete request omits productId, provides a productId that is not a string, or provides a productId whose length is 0 or greater than 256 characters, THEN THE Delete_Product_Lambda SHALL return an HTTP 400 response with error code "MISSING_PARAMS" and a response body indicating that a valid productId is required.
6. IF no Product_Record in the Products_Table has a productId equal to the requested productId, THEN THE Delete_Product_Lambda SHALL return an HTTP 404 response with error code "NOT_FOUND" and a response body indicating that the requested product does not exist.
7. IF the request body is not valid JSON, THEN THE Delete_Product_Lambda SHALL return an HTTP 400 response with error code "INVALID_JSON" and a descriptive message.
8. IF a Products_Table update attempt fails due to a transient DynamoDB error, THEN THE Delete_Product_Lambda SHALL retry the update up to 3 total attempts before returning an error response.
9. IF the Products_Table update fails after all retry attempts are exhausted, THEN THE Delete_Product_Lambda SHALL return an HTTP 500 response with error code "INTERNAL_ERROR" and log the error without exposing internal details to the client.

### Requirement 3: Exclude Soft-Deleted Products from the Inventory Listing

**User Story:** As a household manager, I want soft-deleted products to disappear from my inventory view, so that I only see the products I currently have.

#### Acceptance Criteria

1. WHEN the list-products endpoint returns the inventory, THE list-products Lambda SHALL exclude every Product_Record whose `deleted` attribute is true.
2. WHERE a Product_Record has no `deleted` attribute or has `deleted` set to false, THE list-products Lambda SHALL include that Product_Record in the returned inventory.
3. THE exclusion of soft-deleted products SHALL be applied consistently so that a product hidden by a soft delete does not reappear in subsequent inventory listings.

Note: This requirement introduces a change to the EXISTING list-products Lambda (adding a filter that excludes records whose `deleted` attribute is true). The design and tasks phases MUST account for modifying the existing list-products Lambda, not only creating the new update-product and delete-product Lambdas.

### Requirement 4: Edit a Product from the Inventory Dashboard

**User Story:** As a household manager, I want an Edit control on each product card, so that I can update a product's details directly from where I view my inventory.

#### Acceptance Criteria

1. WHEN a product card is rendered in the Inventory_Dashboard, THE Inventory_Dashboard SHALL display an Edit control on that card.
2. WHEN the user activates the Edit control on a product card, THE Frontend_App SHALL open the Edit_Form pre-filled with that product's current productName, brand, presentation, and expirationDate values.
3. WHEN the user submits the Edit_Form, THE Frontend_App SHALL send a request to the /update-product endpoint including the product's productId and the Editable_Fields.
4. WHILE the update request is in progress, THE Frontend_App SHALL disable the Edit_Form submit control and display a loading indicator until a response is received or the 30-second request timeout elapses.
5. WHEN the /update-product endpoint returns a success response, THE Frontend_App SHALL close the Edit_Form and display the updated productName, brand, presentation, and expirationDate values on the corresponding product card in the Inventory_Dashboard.
6. IF the /update-product endpoint returns an error response or the 30-second request timeout elapses, THEN THE Frontend_App SHALL display an error message indicating the update failed, keep the Edit_Form open with the user-entered values retained, and re-enable the submit control so the user can retry.
7. IF the user submits the Edit_Form when productName is empty after trimming leading and trailing whitespace, THEN THE Frontend_App SHALL block the submission, retain all user-entered values, and display a validation message indicating that productName is required.
8. IF the user submits the Edit_Form when productName exceeds 200 characters after trimming, THEN THE Frontend_App SHALL block the submission, retain all user-entered values, and display a validation message indicating the productName length limit.

### Requirement 5: Delete a Product from the Inventory Dashboard with Confirmation

**User Story:** As a household manager, I want a Delete control that asks me to confirm, so that I remove products intentionally and avoid accidental deletion.

#### Acceptance Criteria

1. WHEN a product card is rendered in the Inventory_Dashboard, THE Inventory_Dashboard SHALL display a Delete control on that card that is reachable by keyboard focus and has an accessible name identifying it as a delete action for that product.
2. WHEN the user activates the Delete control on a product card, THE Frontend_App SHALL display a Delete_Confirmation that displays the product's name and moves keyboard focus into the Delete_Confirmation.
3. WHILE the Delete_Confirmation is displayed, THE Frontend_App SHALL confine keyboard focus to the Delete_Confirmation controls and expose it to assistive technologies as a modal dialog.
4. WHEN the user confirms the Delete_Confirmation, THE Frontend_App SHALL send a request to the /delete-product endpoint including the product's productId.
5. WHEN the user dismisses the Delete_Confirmation without confirming, THE Frontend_App SHALL close the Delete_Confirmation, cancel the deletion, leave the product unchanged in the Inventory_Dashboard, and return keyboard focus to the Delete control that opened it.
6. WHILE the delete request is in progress, THE Frontend_App SHALL display a loading indicator within the Delete_Confirmation and disable the confirm and dismiss controls until a response is received or the request times out after 10 seconds.
7. WHEN the /delete-product endpoint returns a success response within 10 seconds, THE Frontend_App SHALL remove the deleted product's card from the Inventory_Dashboard and close the Delete_Confirmation.
8. IF the /delete-product endpoint returns an error response or the request does not complete within 10 seconds, THEN THE Frontend_App SHALL display an error message indicating the deletion failed, keep the product's card visible in the Inventory_Dashboard, and re-enable the confirm and dismiss controls.

### Requirement 6: Update and Delete API Infrastructure

**User Story:** As a developer, I want the update-product and delete-product Lambdas and their API routes defined as infrastructure-as-code, so that they are provisioned consistently with the rest of the system.

#### Acceptance Criteria

1. THE Update_Product_Lambda and the Delete_Product_Lambda SHALL be defined in a CloudFormation template stored in the /infra directory, following the same structure as the existing Lambda stack templates.
2. THE Upload_API SHALL expose a method on the /update-product resource path that integrates with the Update_Product_Lambda using AWS_PROXY integration, and an OPTIONS method returning CORS preflight headers.
3. THE Upload_API SHALL expose a method on the /delete-product resource path that integrates with the Delete_Product_Lambda using AWS_PROXY integration, and an OPTIONS method returning CORS preflight headers.
4. WHEN the Update_Product_Lambda or the Delete_Product_Lambda is invoked via API Gateway, THE invoked Lambda SHALL include CORS headers (Access-Control-Allow-Origin: *) in every response.

### Requirement 7: Consistent Authorization for Update and Delete Endpoints

**User Story:** As a developer, I want the new endpoints to use the same authorization model as the existing endpoints, so that the security model stays consistent across the API.

#### Acceptance Criteria

1. THE /update-product method and the /delete-product method on the Upload_API SHALL use AWS_IAM authorization, consistent with the existing PantryVision endpoints.
2. WHEN the Frontend_App sends a request to the /update-product or /delete-product endpoint, THE Frontend_App SHALL sign the request with SigV4 credentials obtained from the Cognito Identity Pool, consistent with the existing endpoints.

### Requirement 8: Least-Privilege Execution Roles

**User Story:** As a developer, I want the update and delete Lambdas to have only the minimum required permissions, so that the system follows the principle of least privilege.

#### Acceptance Criteria

1. THE Update_Product_Lambda execution role SHALL have permission to update items (dynamodb:UpdateItem, or dynamodb:PutItem when the implementation uses a full-item write) on the Products_Table only.
2. THE Delete_Product_Lambda execution role SHALL have permission to update items (dynamodb:UpdateItem) on the Products_Table only, in order to set the Deletion_Attributes on a Product_Record.
3. WHERE the Delete_Product_Lambda must detect a non-existent Product_Record, THE Delete_Product_Lambda SHALL use a dynamodb:UpdateItem call with a condition expression that requires the productId to exist, so that the not-found case is handled without requiring dynamodb:GetItem or dynamodb:DeleteItem permissions.
4. THE Update_Product_Lambda execution role and the Delete_Product_Lambda execution role SHALL each have the AWSLambdaBasicExecutionRole managed policy for CloudWatch Logs access and no permissions beyond those specified in criteria 1 through 3.
5. THE Update_Product_Lambda and the Delete_Product_Lambda SHALL NOT write credentials, secrets, or personally identifiable information to CloudWatch Logs.

## Future Considerations

- **Changing the product photo** is intentionally out of scope. This feature preserves imageKey on update. A future iteration could add a re-upload flow that replaces the S3 image (uploading a new object, updating imageKey, and cleaning up the previous image).
- **Restore / trash view** is a future feature. A future iteration could let the user view and restore soft-deleted products through a "trash" or "recently deleted" view, and/or add a scheduled cleanup job that permanently purges Product_Records soft-deleted more than N days ago (and their associated S3 images). This is out of scope for now.
- **Optimistic concurrency** (e.g., a version attribute to detect concurrent edits) is out of scope for the single-user MVP and could be added if multi-user editing is introduced.
