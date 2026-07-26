# Design Document: Save Product to Inventory

## Architecture Overview

This feature adds a new endpoint to persist confirmed product data to a DynamoDB inventory table. The flow is:

1. User confirms product data in the ReviewForm (frontend)
2. Frontend calls `POST /save-product` with the confirmed data + imageKey
3. A new Lambda function validates the payload, generates a productId (UUID v4), sets createdAt, applies defaults, and writes the record to DynamoDB
4. The Lambda returns the complete Product_Record to the frontend
5. Frontend transitions to the "done" state

The infrastructure follows the existing pattern: one CloudFormation stack per Lambda (with its own API Gateway REST API), plus a new stack for the DynamoDB table.

```
┌──────────────┐     POST /save-product      ┌─────────────────────┐     PutItem     ┌──────────────────────┐
│  Frontend    │ ───────────────────────────► │  Save_Product_Lambda │ ──────────────► │  Products_Table      │
│  (React)     │ ◄─────────────────────────── │  (Python 3.12)       │ ◄────────────── │  (DynamoDB On-Demand)│
│              │     200 { Product_Record }    │                      │                 │                      │
└──────────────┘                              └─────────────────────┘                 └──────────────────────┘
```

## Components

### 1. Backend: Save Product Lambda (`/backend/save-product/handler.py`)

Single-responsibility Lambda that validates, enriches, and persists a product record.

**Responsibilities:**
- Parse and validate the incoming JSON body
- Reject invalid payloads with appropriate error codes (400)
- Generate UUID v4 productId
- Set createdAt to current UTC timestamp in ISO 8601 format
- Apply default values (quantity=1, unit="unit") for omitted optional fields
- Write the Product_Record to DynamoDB
- Return the complete record on success (200)
- Return CORS headers on every response

### 2. Frontend: Product Service (`/frontend/src/services/productService.ts`)

A service module that encapsulates the save-product API call, following the same pattern as `extractionService.ts`.

**Responsibilities:**
- Call `POST /save-product` with the confirmed product data and imageKey
- Handle success (return Product_Record) and error (throw typed error) responses
- Read the API endpoint from `VITE_SAVE_API_ENDPOINT` environment variable

### 3. Frontend: App.tsx Updates

- Store `objectKey` from the upload step in state
- Pass `objectKey` to the confirm handler
- Call `saveProduct()` service on confirm, showing a loading indicator
- Transition to "done" on success, show error on failure

### 4. Infrastructure: DynamoDB Products Table (`/infra/dynamodb-products.yaml`)

CloudFormation template for the pantryvision-products table.

### 5. Infrastructure: Save Product Lambda Stack (`/infra/lambda-save-product.yaml`)

CloudFormation template following the existing pattern (lambda-extract.yaml): Lambda function, IAM role, API Gateway REST API, POST + OPTIONS methods, deployment.

## Interfaces

### API Contract

**Endpoint:** `POST /save-product`

**Request Body:**
```json
{
  "productName": "string (required)",
  "brand": "string (optional, defaults to empty string)",
  "presentation": "string (optional, defaults to empty string)",
  "expirationDate": "string YYYY-MM-DD (optional, defaults to empty string)",
  "imageKey": "string (required, UUID-with-extension format)",
  "quantity": "integer (optional, defaults to 1, must be positive)",
  "unit": "string (optional, defaults to \"unit\")"
}
```

**Success Response (200):**
```json
{
  "productId": "uuid-v4-string",
  "productName": "Coca-Cola",
  "brand": "Coca-Cola Company",
  "presentation": "600ml",
  "expirationDate": "2025-12-31",
  "imageKey": "a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg",
  "createdAt": "2025-01-15T10:30:00Z",
  "quantity": 1,
  "unit": "unit"
}
```

**Error Responses:**

| Status | Error Code | Condition |
|--------|-----------|-----------|
| 400 | MISSING_PARAMS | productName or imageKey missing |
| 400 | INVALID_IMAGE_KEY | imageKey doesn't match UUID-extension pattern |
| 400 | INVALID_QUANTITY | quantity is not a positive integer |
| 500 | INTERNAL_ERROR | DynamoDB write failure |

**Error Response Body:**
```json
{
  "error": "MISSING_PARAMS",
  "message": "Missing required fields: productName, imageKey"
}
```

### Frontend Service Interface

```typescript
// /frontend/src/services/productService.ts

export interface SaveProductRequest {
  productName: string;
  brand: string;
  presentation: string;
  expirationDate: string;
  imageKey: string;
  quantity?: number;
  unit?: string;
}

export interface SaveProductResponse {
  productId: string;
  productName: string;
  brand: string;
  presentation: string;
  expirationDate: string;
  imageKey: string;
  createdAt: string;
  quantity: number;
  unit: string;
}

export type SaveProductErrorCode =
  | 'MISSING_PARAMS'
  | 'INVALID_IMAGE_KEY'
  | 'INVALID_QUANTITY'
  | 'INTERNAL_ERROR'
  | 'UNKNOWN';

export class SaveProductError extends Error {
  code: SaveProductErrorCode;
  constructor(code: SaveProductErrorCode, message: string);
}

export async function saveProduct(request: SaveProductRequest): Promise<SaveProductResponse>;
```

### Lambda Handler Interface

```python
# /backend/save-product/handler.py

def lambda_handler(event: dict, context) -> dict:
    """
    POST /save-product
    Body: { productName, brand?, presentation?, expirationDate?, imageKey, quantity?, unit? }
    Returns: Product_Record (200) or error response (400/500)
    """
    ...

def validate_request(body: dict) -> dict | None:
    """Returns error response dict if validation fails, None if valid."""
    ...

def build_product_record(body: dict) -> dict:
    """Generates productId, createdAt, applies defaults, returns complete record."""
    ...

def build_success_response(record: dict) -> dict:
    """HTTP 200 response with CORS headers."""
    ...

def build_error_response(status_code: int, error_code: str, message: str) -> dict:
    """HTTP error response with CORS headers."""
    ...
```

## Data Models

### DynamoDB: pantryvision-products

| Attribute | Type | Description |
|-----------|------|-------------|
| productId | String (PK) | UUID v4, generated server-side |
| productName | String | Required, non-empty |
| brand | String | Optional, may be empty |
| presentation | String | Optional, may be empty |
| expirationDate | String | YYYY-MM-DD format or empty |
| imageKey | String | Required, UUID.extension format |
| createdAt | String | ISO 8601 UTC (e.g., 2025-01-15T10:30:00Z) |
| quantity | Number | Positive integer, default 1 |
| unit | String | Default "unit" |

**Key Schema:**
- Partition Key: `productId` (String)
- No Sort Key (simple primary key for MVP)

**Billing Mode:** PAY_PER_REQUEST (On-Demand)

**Encryption:** SSE with AWS-owned keys (default)

### Validation Rules

| Field | Rule |
|-------|------|
| productName | Required, non-empty string after trimming |
| imageKey | Required, matches regex `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg\|jpeg\|png\|webp)$` |
| quantity | If provided, must be a positive integer (> 0) |
| brand | Optional string, defaults to "" |
| presentation | Optional string, defaults to "" |
| expirationDate | Optional string, expected YYYY-MM-DD or "" |
| unit | Optional string, defaults to "unit" |

## Error Handling

### Backend (Lambda)

1. **Invalid JSON body:** Return 400 with `INVALID_JSON` error code (defensive, in case API Gateway passes malformed body)
2. **Missing required fields:** Return 400 with `MISSING_PARAMS`, message lists which fields are missing
3. **Invalid imageKey format:** Return 400 with `INVALID_IMAGE_KEY`
4. **Invalid quantity:** Return 400 with `INVALID_QUANTITY`
5. **DynamoDB write failure:** Log the full exception (no PII), return 500 with `INTERNAL_ERROR` and generic message
6. **Unexpected exception:** Catch-all, log with `logger.exception`, return 500 with `INTERNAL_ERROR`

All error responses include CORS headers to ensure the browser can read the error.

### Frontend

1. **Network failure:** Catch fetch error, display generic "Could not save product" message, stay on review screen
2. **HTTP 4xx/5xx:** Parse error body, display the message to the user, stay on review screen for retry
3. **Timeout:** Rely on browser's default timeout, handle the same as network failure

## Infrastructure Details

### `/infra/dynamodb-products.yaml`

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: PantryVision - DynamoDB Products Table for inventory storage.

Parameters:
  TableName:
    Type: String
    Default: pantryvision-products

Resources:
  ProductsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Ref TableName
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: productId
          AttributeType: S
      KeySchema:
        - AttributeName: productId
          KeyType: HASH
      SSESpecification:
        SSEEnabled: true

Outputs:
  TableName:
    Value: !Ref ProductsTable
  TableArn:
    Value: !GetAtt ProductsTable.Arn
```

### `/infra/lambda-save-product.yaml`

Follows the same structure as `lambda-extract.yaml`:
- IAM Role with `AWSLambdaBasicExecutionRole` + `dynamodb:PutItem` on the products table only
- Lambda function (Python 3.12, 128MB, 10s timeout)
- API Gateway REST API with POST /save-product and OPTIONS /save-product (CORS)
- Lambda permission for API Gateway invocation
- Deployment to prod stage

Environment variables:
- `TABLE_NAME`: DynamoDB table name (parameter with default `pantryvision-products`)

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Valid payload round-trip preservation

*For any* valid save-product request (with productName non-empty, imageKey matching UUID-extension pattern, and optional fields in valid range), invoking the Save_Product_Lambda SHALL return an HTTP 200 response whose body contains: a valid UUID v4 `productId`, a valid ISO 8601 UTC `createdAt` timestamp, and all input field values (productName, brand, presentation, expirationDate, imageKey, quantity, unit) preserved exactly as provided.

**Validates: Requirements 1.1, 1.2, 2.3**

### Property 2: Default values applied for omitted optional fields

*For any* valid save-product request that omits the `quantity` field, the response SHALL contain `quantity: 1`. *For any* valid save-product request that omits the `unit` field, the response SHALL contain `unit: "unit"`.

**Validates: Requirements 2.1, 2.2**

### Property 3: Missing required fields rejected

*For any* request body that is missing `productName` or `imageKey` (or both), the Save_Product_Lambda SHALL return an HTTP 400 response with error code `"MISSING_PARAMS"` and SHALL NOT write to DynamoDB.

**Validates: Requirements 1.3**

### Property 4: Invalid imageKey rejected

*For any* request body where `imageKey` is a non-empty string that does NOT match the UUID-with-extension pattern (`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|jpeg|png|webp)$`), the Save_Product_Lambda SHALL return an HTTP 400 response with error code `"INVALID_IMAGE_KEY"` and SHALL NOT write to DynamoDB.

**Validates: Requirements 1.4**

### Property 5: Invalid quantity rejected

*For any* request body where `quantity` is provided but is not a positive integer (e.g., zero, negative, float, or non-numeric), the Save_Product_Lambda SHALL return an HTTP 400 response with error code `"INVALID_QUANTITY"` and SHALL NOT write to DynamoDB.

**Validates: Requirements 2.4**

### Property 6: CORS headers present in every response

*For any* invocation of the Save_Product_Lambda (whether resulting in 200, 400, or 500 status), the response headers SHALL include `Access-Control-Allow-Origin: *`.

**Validates: Requirements 5.3**

### Property 7: Frontend saveProduct transmits all required fields

*For any* `SaveProductRequest` object passed to the `saveProduct()` function, the outgoing HTTP request body SHALL include `productName`, `brand`, `presentation`, `expirationDate`, and `imageKey` fields with the exact values provided in the input object.

**Validates: Requirements 3.1**
