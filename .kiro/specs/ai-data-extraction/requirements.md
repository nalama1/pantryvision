# Requirements Document

## Introduction

The AI Data Extraction module enables PantryVision to automatically extract structured product data from uploaded photos using Amazon Bedrock's vision model. After a user uploads a product photo (via the existing upload-product-photo feature), the system analyzes the image and returns extracted fields (product name, brand, presentation, expiration date) for user review. The user confirms or manually corrects the data before it proceeds to inventory storage. This module enforces the architecture rule that AI is never a blocking requirement — manual entry is always available as a fallback.

## Glossary

- **Extraction_Lambda**: The AWS Lambda function (Python 3.12) responsible for receiving an S3 object key, retrieving the image from S3, invoking Amazon Bedrock, and returning structured extraction results.
- **Bedrock_Vision_Model**: The Amazon Bedrock vision-capable model (Amazon Nova Pro) used to analyze product images and extract structured data.
- **Extraction_Result**: A JSON object containing the extracted product fields (productName, brand, presentation, expirationDate) along with per-field confidence indicators.
- **Confidence_Indicator**: A value (high, medium, low) associated with each extracted field indicating the model's certainty about the extraction accuracy.
- **Review_Form**: The frontend React component that displays the extracted data in editable fields for user confirmation or manual correction.
- **Product_Data**: The structured data object containing productName, brand, presentation, and expirationDate fields ready for inventory storage.
- **S3_Object_Key**: The unique identifier (UUID-based filename) for a product image stored in the pantryvision-product-images S3 bucket.

## Requirements

### Requirement 1: Invoke AI Extraction

**User Story:** As a user, I want the system to automatically extract product data from my uploaded photo, so that I do not have to type all product details manually.

#### Acceptance Criteria

1. WHEN the frontend sends a POST request to `/extract-product-data` with a valid S3_Object_Key, THE Extraction_Lambda SHALL retrieve the corresponding image from the pantryvision-product-images S3 bucket.
2. WHEN the Extraction_Lambda retrieves the image, THE Extraction_Lambda SHALL invoke the Bedrock_Vision_Model with a structured prompt requesting JSON output containing productName, brand, presentation, and expirationDate fields.
3. WHEN the Bedrock_Vision_Model returns a response, THE Extraction_Lambda SHALL parse the response and return an Extraction_Result to the frontend within 15 seconds of the original request.
4. THE Extraction_Lambda SHALL use IAM role-based permissions to access both the S3 bucket and Bedrock_Vision_Model without hardcoded credentials.

### Requirement 2: Structured Data Output

**User Story:** As a user, I want the extracted data to be returned in a consistent format, so that the review form can reliably display it.

#### Acceptance Criteria

1. THE Extraction_Lambda SHALL return an Extraction_Result containing exactly four fields: productName (string), brand (string), presentation (string), and expirationDate (string in ISO 8601 format YYYY-MM-DD).
2. WHEN the Bedrock_Vision_Model returns an expiration date in any format, THE Extraction_Lambda SHALL normalize the date to ISO 8601 format (YYYY-MM-DD) before returning the Extraction_Result.
3. WHEN the Bedrock_Vision_Model cannot determine a field value, THE Extraction_Lambda SHALL return that field as null in the Extraction_Result.
4. THE Extraction_Lambda SHALL include a Confidence_Indicator (high, medium, or low) for each extracted field in the Extraction_Result.

### Requirement 3: Graceful AI Failure Handling

**User Story:** As a user, I want to manually enter product data when AI cannot extract it, so that I can always add products to my inventory regardless of image quality.

#### Acceptance Criteria

1. IF the Bedrock_Vision_Model returns an error or times out, THEN THE Extraction_Lambda SHALL return a response with all fields set to null and all confidence indicators set to low, along with a descriptive error message.
2. IF the S3_Object_Key does not correspond to an existing image, THEN THE Extraction_Lambda SHALL return a 404 error with error code "IMAGE_NOT_FOUND" and a descriptive message.
3. IF the Bedrock_Vision_Model returns partial data (some fields extracted, some not), THEN THE Extraction_Lambda SHALL return the successfully extracted fields with their confidence indicators and set unextracted fields to null.
4. IF the request body is missing the S3_Object_Key parameter, THEN THE Extraction_Lambda SHALL return a 400 error with error code "MISSING_PARAMS" and a descriptive message.

### Requirement 4: User Review and Confirmation

**User Story:** As a user, I want to review and correct the AI-extracted data before it is saved, so that I can ensure accuracy of my inventory records.

#### Acceptance Criteria

1. WHEN the frontend receives an Extraction_Result, THE Review_Form SHALL display each extracted field in an editable input control pre-filled with the extracted value (or empty if the value is null).
2. WHEN a field has a Confidence_Indicator of low, THE Review_Form SHALL visually highlight that field to indicate it may need manual correction.
3. THE Review_Form SHALL allow the user to edit any extracted field before submission regardless of the Confidence_Indicator value.
4. WHEN the user submits the Review_Form, THE Review_Form SHALL validate that productName is not empty before producing the confirmed Product_Data.
5. WHEN the user submits the Review_Form with valid data, THE Review_Form SHALL produce a Product_Data object containing productName, brand, presentation, and expirationDate ready for inventory storage.

### Requirement 5: Extraction Prompt Engineering

**User Story:** As a developer, I want the Bedrock prompt to reliably extract structured JSON, so that extraction results are consistent and parseable.

#### Acceptance Criteria

1. THE Extraction_Lambda SHALL send a prompt to the Bedrock_Vision_Model that explicitly requests a JSON response containing productName, brand, presentation, and expirationDate fields.
2. THE Extraction_Lambda SHALL include in the prompt clear definitions for each field: productName (the product name as shown on packaging), brand (the manufacturer or brand name), presentation (the product format or size such as "500ml" or "1kg"), and expirationDate (the expiration or best-before date found on packaging).
3. THE Extraction_Lambda SHALL instruct the Bedrock_Vision_Model to return null for any field it cannot determine from the image.
4. THE Extraction_Lambda SHALL instruct the Bedrock_Vision_Model to include a confidence level (high, medium, or low) for each extracted field.

### Requirement 6: Cost and Performance Optimization

**User Story:** As a project owner, I want the extraction to use cost-effective resources while maintaining acceptable performance, so that the system remains affordable for personal use.

#### Acceptance Criteria

1. THE Extraction_Lambda SHALL use the most cost-effective Bedrock vision model that provides acceptable extraction accuracy (Amazon Nova Pro as default, configurable via environment variable).
2. THE Extraction_Lambda SHALL set a timeout of 30 seconds for the Bedrock_Vision_Model invocation to prevent excessive costs from hung requests.
3. THE Extraction_Lambda SHALL log the model invocation duration and token usage for cost monitoring.
4. THE Extraction_Lambda SHALL configure its own execution timeout to 60 seconds to accommodate the Bedrock call plus S3 retrieval overhead.

### Requirement 7: API Security and Validation

**User Story:** As a user, I want the extraction endpoint to be secure, so that unauthorized parties cannot access my product images or abuse the AI service.

#### Acceptance Criteria

1. THE Extraction_Lambda SHALL validate that the provided S3_Object_Key matches the expected format (UUID followed by a valid image file extension) before processing.
2. THE Extraction_Lambda SHALL return a 400 error with error code "INVALID_OBJECT_KEY" if the S3_Object_Key format is invalid.
3. THE Extraction_Lambda SHALL include CORS headers (Access-Control-Allow-Origin) in all responses to support frontend requests.
4. IF an unexpected error occurs during processing, THEN THE Extraction_Lambda SHALL log the full error details and return a 500 error with error code "INTERNAL_ERROR" and a generic message without exposing internal details.
