# Design Document: Inventory Dashboard

## Architecture Overview

This feature adds a read path to PantryVision's inventory: a new Lambda scans the products table, enriches each item with a presigned image URL, and returns a sorted list. The frontend gets a new "My Inventory" view and a simple nav bar to switch between it and the existing Upload flow.

```
┌──────────────┐   GET /list-products    ┌───────────────────────┐   Scan    ┌──────────────────────┐
│  Frontend    │ ───────────────────────►│  List_Products_Lambda │ ─────────►│  Products_Table      │
│  (React)     │                         │  (Python 3.12)        │◄─────────┤  (DynamoDB On-Demand)│
│  Nav_Bar +   │◄─────────────────────── │                        │           └──────────────────────┘
│  Inventory_  │  200 [ { ...,imageUrl } ]│                       │  generate_presigned_url
│  Dashboard   │                         │                       │──────────►┌──────────────────────┐
└──────────────┘                         └───────────────────────┘           │ Product_Images_Bucket│
                                                                              │ (S3, private)         │
                                                                              └──────────────────────┘
```

Flow:
1. User clicks "My Inventory" in the Nav_Bar.
2. `Inventory_Dashboard` calls `GET /list-products`.
3. `List_Products_Lambda` scans `Products_Table`, generates a presigned GET URL (300s TTL) per item with a non-empty `imageKey`, sorts by `expirationDate` (soonest first, blanks last), and returns the array.
4. `Inventory_Dashboard` renders product cards, applying an "expiring soon" or "expired" highlight based on each item's `expirationDate` relative to today.

The infrastructure follows the existing per-Lambda CloudFormation stack pattern (own API Gateway REST API, IAM role, deployment).

## Components

### 1. Backend: List Products Lambda (`/backend/list-products/handler.py`)

Single-responsibility Lambda that reads and enriches product records for display.

**Responsibilities:**
- Scan `Products_Table` for all items
- For each item with a non-empty `imageKey`, call `s3_client.generate_presigned_url` (GET, 300s expiration) and attach as `imageUrl`; otherwise set `imageUrl` to `null`
- Sort items by `expirationDate` ascending, with empty `expirationDate` items placed last
- Return the sorted array in an HTTP 200 response with CORS headers
- Handle DynamoDB scan failures gracefully (500, `INTERNAL_ERROR`, no internal detail leakage)

### 2. Frontend: Inventory Service (`/frontend/src/services/inventoryService.ts`)

Encapsulates the `/list-products` call, following the same pattern as `productService.ts`.

**Responsibilities:**
- Call `GET /list-products`
- Return a typed array of `InventoryProduct` on success
- Throw a typed `ListProductsError` on failure
- Read the API endpoint from `VITE_LIST_API_ENDPOINT`

### 3. Frontend: Inventory Dashboard (`/frontend/src/components/InventoryDashboard/InventoryDashboard.tsx`)

New component that fetches and renders the product grid.

**Responsibilities:**
- On mount, call `listProducts()`; track `loading`, `error`, and `products` state
- Render a loading indicator while the request is in flight
- Render an error message with a retry button on failure
- Render an empty-state message when the array is empty
- Render one `ProductCard` per item
- Compute an expiration classification (`expired` | `expiring-soon` | `normal`) per item using a pure helper function and apply it as a CSS class

### 4. Frontend: Product Card (sub-component within `InventoryDashboard`)

Renders a single product's image (or placeholder), name, brand, presentation, expiration date, and quantity/unit, with the highlight class applied to the card container.

### 5. Frontend: Nav Bar (`/frontend/src/components/NavBar/NavBar.tsx`)

Simple tab-style navigation with two buttons: "Upload" and "My Inventory". Calls a callback prop when a tab is selected; the active tab is controlled by `App.tsx` state. No routing library is introduced.

### 6. Frontend: App.tsx Updates

- Add `view` state (`'upload' | 'inventory'`), defaulting to `'upload'`
- Render `NavBar` above the main content, wired to update `view`
- Render the existing Upload flow when `view === 'upload'`, and `InventoryDashboard` when `view === 'inventory'`
- Preserve existing upload/review/done state machine unchanged

### 7. Infrastructure: List Products Lambda Stack (`/infra/lambda-list-products.yaml`)

CloudFormation template following the existing pattern (`lambda-save-product.yaml`): Lambda function, IAM role (`dynamodb:Scan` on the products table + `s3:GetObject` on the images bucket), API Gateway REST API with GET + OPTIONS `/list-products`, Lambda permission, deployment.

## Interfaces

### API Contract

**Endpoint:** `GET /list-products`

**Success Response (200):**
```json
[
  {
    "productId": "a1b2c3d4-...",
    "productName": "Coca-Cola",
    "brand": "Coca-Cola Company",
    "presentation": "600ml",
    "expirationDate": "2025-12-31",
    "imageKey": "e5f6g7h8-....jpg",
    "imageUrl": "https://pantryvision-product-images.s3.amazonaws.com/e5f6g7h8-....jpg?X-Amz-...",
    "createdAt": "2025-01-15T10:30:00Z",
    "quantity": 2,
    "unit": "unit"
  }
]
```

**Error Response (500):**
```json
{
  "error": "INTERNAL_ERROR",
  "message": "Failed to retrieve products"
}
```

### Lambda Handler Interface

```python
# /backend/list-products/handler.py

def lambda_handler(event: dict, context) -> dict:
    """
    GET /list-products
    Returns: HTTP 200 with a JSON array of Product_Record + imageUrl, sorted by
    expirationDate ascending (empty dates last), or HTTP 500 on scan failure.
    """
    ...

def scan_all_products() -> list[dict]:
    """Scans Products_Table, handling pagination (LastEvaluatedKey) internally."""
    ...

def enrich_with_image_url(item: dict) -> dict:
    """
    Returns a copy of item with 'imageUrl' set: a presigned GET URL (300s TTL)
    if imageKey is non-empty, otherwise None.
    """
    ...

def sort_by_expiration(items: list[dict]) -> list[dict]:
    """
    Returns items sorted ascending by expirationDate; items with an empty
    expirationDate are placed after all items with a non-empty expirationDate.
    """
    ...

def build_success_response(items: list[dict]) -> dict:
    """HTTP 200 response with CORS headers and JSON array body."""
    ...

def build_error_response(status_code: int, error_code: str, message: str) -> dict:
    """HTTP error response with CORS headers."""
    ...
```

### Frontend Service Interface

```typescript
// /frontend/src/services/inventoryService.ts

export interface InventoryProduct {
  productId: string;
  productName: string;
  brand: string;
  presentation: string;
  expirationDate: string;
  imageKey: string;
  imageUrl: string | null;
  createdAt: string;
  quantity: number;
  unit: string;
}

export type ListProductsErrorCode = 'INTERNAL_ERROR' | 'UNKNOWN';

export class ListProductsError extends Error {
  code: ListProductsErrorCode;
  constructor(code: ListProductsErrorCode, message: string);
}

export async function listProducts(): Promise<InventoryProduct[]>;
```

### Frontend Expiration Classification Helper

```typescript
// /frontend/src/components/InventoryDashboard/expirationStatus.ts

export type ExpirationStatus = 'expired' | 'expiring-soon' | 'normal';

/**
 * Classifies a product's expiration status relative to the current date.
 * - 'expired': expirationDate is before today
 * - 'expiring-soon': expirationDate is today through 7 days from today (inclusive)
 * - 'normal': expirationDate is more than 7 days away, or empty
 */
export function getExpirationStatus(expirationDate: string, today: Date): ExpirationStatus;
```

### Component Props

```typescript
// NavBar.tsx
export interface NavBarProps {
  activeView: 'upload' | 'inventory';
  onSelectView: (view: 'upload' | 'inventory') => void;
}

// InventoryDashboard.tsx
export interface InventoryDashboardProps {} // fetches its own data on mount
```

## Data Models

No new persisted data model — `list-products` reads the existing `pantryvision-products` schema (see `save-product-inventory` spec) and adds a derived, non-persisted `imageUrl` field to each item in the API response only.

| Attribute | Type | Source |
|-----------|------|--------|
| productId | String | Products_Table |
| productName | String | Products_Table |
| brand | String | Products_Table |
| presentation | String | Products_Table |
| expirationDate | String (YYYY-MM-DD or "") | Products_Table |
| imageKey | String | Products_Table |
| imageUrl | String \| null | Derived at request time (presigned URL or null) |
| createdAt | String (ISO 8601 UTC) | Products_Table |
| quantity | Number | Products_Table |
| unit | String | Products_Table |

## Error Handling

### Backend (Lambda)

1. **DynamoDB scan failure:** Catch `ClientError`, log the exception (no PII), return 500 `INTERNAL_ERROR` with a generic message.
2. **S3 presign failure for a single item:** Catch the error for that item only, log it, and set `imageUrl` to `null` for that item rather than failing the whole request (keeps the AI/data-display path non-blocking, consistent with the "AI never blocks" principle applied to image loading).
3. **Unexpected exception:** Catch-all, log with `logger.exception`, return 500 `INTERNAL_ERROR`.
4. All responses (success and error) include `Access-Control-Allow-Origin: *`.

### Frontend

1. **Network failure / non-200 response:** `listProducts()` throws `ListProductsError`; `InventoryDashboard` catches it, shows an error message and a "Retry" button that re-triggers the fetch.
2. **Empty array:** Not an error — render a friendly empty-state message ("No products saved yet").
3. **Missing/null imageUrl:** Render a placeholder image element instead of a broken `<img>` tag.

## Infrastructure Details

### `/infra/lambda-list-products.yaml`

Follows the same structure as `lambda-save-product.yaml`:
- IAM Role: `AWSLambdaBasicExecutionRole` managed policy + inline policy granting `dynamodb:Scan` on the products table ARN only, and `s3:GetObject` on the images bucket ARN (`arn:aws:s3:::pantryvision-product-images/*`) only
- Lambda function: Python 3.12, 128MB, 10s timeout, env vars `TABLE_NAME` and `BUCKET_NAME`
- API Gateway REST API with `GET /list-products` (AWS_PROXY integration) and `OPTIONS /list-products` (CORS mock integration)
- Lambda permission for API Gateway invocation
- Deployment to `prod` stage
- `AuthorizationType: NONE` temporarily, matching the existing temporary auth setup on other endpoints (to be switched to `AWS_IAM` later, per tech steering)

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Scan returns every stored record

*For any* set of Product_Record items present in the Products_Table (including zero items), invoking the List_Products_Lambda SHALL return an HTTP 200 response whose body is a JSON array containing exactly one entry per stored record, with no records omitted or duplicated.

**Validates: Requirements 1.1, 1.4**

### Property 2: Presigned URL generation depends only on imageKey presence

*For any* Product_Record, the enriched item's `imageUrl` SHALL be a non-null presigned URL string if and only if the record's `imageKey` is a non-empty string; if `imageKey` is empty or missing, `imageUrl` SHALL be `null`.

**Validates: Requirements 1.2, 1.3**

### Property 3: Sort order is ascending by expiration date with blanks last

*For any* list of Product_Record items, the order returned by the List_Products_Lambda SHALL satisfy: (a) every item with a non-empty `expirationDate` appears before every item with an empty `expirationDate`, and (b) among items with a non-empty `expirationDate`, each item's date SHALL be less than or equal to the date of the next item in the list.

**Validates: Requirements 2.1, 2.2**

### Property 4: CORS headers present in every response

*For any* invocation of the List_Products_Lambda (success, empty-list, or error path), the response headers SHALL include `Access-Control-Allow-Origin: *`.

**Validates: Requirements 1.6**

### Property 5: Rendered product card exposes all required fields and correct image source

*For any* `InventoryProduct` object passed to the product card renderer, the rendered output SHALL contain the values of `productName`, `brand`, `presentation`, `expirationDate`, `quantity`, and `unit`; additionally, the rendered image element's source SHALL equal `imageUrl` when it is non-null, and SHALL be the placeholder image when `imageUrl` is `null`.

**Validates: Requirements 3.2, 3.3**

### Property 6: Expiration classification is correct for any date

*For any* `expirationDate` string and reference `today` date, `getExpirationStatus` SHALL return `'expired'` if the parsed date is strictly before `today`, `'expiring-soon'` if the parsed date is on or after `today` and no more than 7 days after `today`, and `'normal'` if the parsed date is more than 7 days after `today` or `expirationDate` is empty.

**Validates: Requirements 4.1, 4.2, 4.3**

## Testing Strategy

- **Property tests** (backend, Python + `hypothesis`, and frontend, TypeScript + `fast-check`) cover Properties 1-6 above with mocked DynamoDB/S3 clients and mocked fetch, at 100+ iterations each.
- **Unit/example tests** cover: empty-table response (1.4 boundary), DynamoDB scan failure (1.5), dashboard fetch wiring and loading/error/empty states (3.1, 3.4-3.6), Nav_Bar rendering and view switching (5.1-5.4).
- **Infrastructure** (IAM least-privilege, CloudFormation resource wiring — Requirements 6.1-6.4) is verified by template review, not automated tests, consistent with the "IaC is not suited to PBT" guidance.
