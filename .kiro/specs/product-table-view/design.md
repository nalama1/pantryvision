# Design Document

## Overview

This feature adds a **spreadsheet-style table view** of the inventory,
complementing the existing card-based `InventoryDashboard` ("My Pantry"). It is
reached from a new `NavBar` tab placed **before** the "My Pantry" tab.

The design is deliberately **frontend-heavy with one small, backward-compatible
backend change**:

- **Frontend (React + TypeScript):**
  - A new `ProductTable` component that renders the inventory as an accessible
    HTML table, with columns: row number, expiration date, name, brand,
    presentation, quantity, expiration status, active/inactive, and an image
    "View" action.
  - Client-side **status filter** (reusing the existing `getExpirationStatus`),
    an **"Show inactive" toggle**, **client-side pagination** (page size 5 / 10
    / 20, default 10), and an **image lightbox** (`ImageViewer`) opened on
    demand per row.
  - A new `NavBar` tab and a third `AppView` value (`'table'`) wired into
    `App.tsx`.
  - The `inventoryService.listProducts` call gains an optional
    `includeDeleted` argument that appends `?includeDeleted=true` to the request;
    the `InventoryProduct` type gains an optional `deleted` field.
- **Backend (Python 3.12, one existing Lambda modified):**
  - `list-products` reads an `includeDeleted` query-string parameter. When it is
    a case-insensitive `"true"`, the soft-delete `FilterExpression` is dropped so
    inactive (soft-deleted) records are returned too; otherwise behavior is
    **exactly** as today. This is the only backend change and requires a
    re-deploy of the `list-products` Lambda.

**Explicitly out of scope** (tracked in the requirements' Future
Considerations): column sorting, server-side pagination, restoring inactive
products, inline/bulk editing, and column selection/export.

### Design principles applied

- **Reuse over reinvention** — the table computes status with the same
  `getExpirationStatus` used by the cards, reuses `signedFetch`, the i18n `t()`
  mechanism, the `Toast`/spinner/modal styling patterns, and the existing
  `InventoryProduct` shape. The two views cannot disagree on status because they
  share the classifier.
- **Serverless, pay-per-use** — no new infrastructure. The only backend change
  is a conditional filter inside an existing Lambda; pagination and filtering are
  client-side, adequate for the expected scale (hundreds of products).
- **Backward compatible** — `includeDeleted` is opt-in. Callers that send no
  parameter (the `InventoryDashboard`) get identical behavior to today; no data
  migration is required.
- **AI never blocks / graceful degradation** — not directly applicable here, but
  the same spirit applies to images: a missing or failed image never breaks the
  table; it degrades to a "no image" / "couldn't load" state.
- **Accessibility first** — semantic table markup, status not conveyed by color
  alone, keyboard-operable "View" actions, and a focus-trapped modal lightbox.

## Architecture

### Component flow

```mermaid
flowchart TD
    subgraph Frontend["Frontend (React + TypeScript)"]
        Nav[NavBar<br/>tabs: Add Item / Table / My Pantry]
        AppC[App.tsx<br/>view: 'upload' | 'table' | 'inventory']
        PT[ProductTable<br/>filter + toggle + pagination]
        Row[Product rows<br/>status label + Active/Inactive + View button]
        IV[ImageViewer<br/>modal lightbox, focus trap]
        Svc[inventoryService.listProducts includeDeleted?]
        ES[getExpirationStatus<br/>shared with InventoryDashboard]
        Signed[signedFetch.ts<br/>SigV4 via Cognito]
    end

    subgraph Gateway["API Gateway (AWS_IAM)"]
        ListRes[/list-products GET<br/>?includeDeleted=true optional/]
    end

    subgraph Lambdas["AWS Lambda (Python 3.12)"]
        ListFn[list-products MODIFIED<br/>reads includeDeleted query param]
    end

    DDB[(DynamoDB<br/>pantryvision-products)]
    S3[(S3 private<br/>pantryvision-product-images)]

    Nav -- "select Table tab" --> AppC
    AppC -- "view === 'table'" --> PT
    PT --> Row
    PT --> Svc
    Row -- "compute status" --> ES
    Row -- "View click" --> IV
    Svc --> Signed
    Signed -- "SigV4 GET (+?includeDeleted)" --> ListRes
    ListRes --> ListFn
    ListFn -- "Scan (+FilterExpression unless includeDeleted)" --> DDB
    ListFn -- "presign GET per imageKey" --> S3
    IV -- "loads presigned imageUrl" --> S3
```

Notes:

- The table calls the **same** `list-products` endpoint the dashboard uses. The
  only difference is the optional `?includeDeleted=true` query parameter, added
  only when the "Show inactive" toggle is checked.
- Pagination and status filtering happen **in the browser** after the full
  (filtered-by-active) list is fetched. This matches the requirements' decision
  to keep pagination client-side at MVP scale.
- Image URLs are the **presigned URLs already returned by `list-products`**
  (`imageUrl`, ~300s TTL). The `ImageViewer` displays that URL; it does not make
  its own presign call. See the "Presigned URL lifetime" decision below.

### Fetch strategy decision (when to re-request)

The "Show inactive" toggle changes **which records the server returns**, so
toggling it requires a **new request** (`includeDeleted=true` vs. the default).
The status filter and pagination, by contrast, operate on already-fetched data
and require **no** network call.

- Unchecked → checked: request with `includeDeleted=true`, show loading, replace
  the list with active + inactive records.
- Checked → unchecked: request without the parameter (or re-use the default),
  show loading, replace the list with active-only records.

Re-fetching on toggle (rather than fetching everything once and filtering
client-side) keeps the default view identical to today's payload and avoids ever
sending inactive records to users who did not ask for them.

### Presigned URL lifetime decision

`list-products` presigns each image URL with a **300-second** TTL. If a user
keeps the table open longer than ~5 minutes and then clicks "View", the URL may
have expired and the image load will fail. The design handles this **gracefully**
rather than pre-emptively: the `ImageViewer` shows a "couldn't load image"
fallback (Req 7.6), and the user can refresh the inventory (the table's
retry/refresh path re-presigns). Proactively refreshing URLs or presigning
per-click is out of scope for the MVP and noted as a possible enhancement; the
graceful fallback satisfies Req 7.6 without extra backend calls.

## Components and Interfaces

### Backend: `list-products` modification

File: `backend/list-products/handler.py`. The change is additive and isolated to
how the `FilterExpression` is chosen.

- `lambda_handler(event, context)` reads the flag:

  ```python
  def _wants_deleted(event: dict) -> bool:
      params = event.get("queryStringParameters") or {}
      value = (params.get("includeDeleted") or "").strip().lower()
      return value == "true"
  ```

  `queryStringParameters` is `None` when no query string is present (API Gateway
  proxy integration), hence the `or {}` guard.

- `scan_all_products(include_deleted: bool = False)` accepts the flag:
  - When `include_deleted` is `False` (default): keep today's
    `FilterExpression = Attr("deleted").not_exists() | Attr("deleted").eq(False)`
    on the initial scan and every paginated follow-up scan (unchanged behavior).
  - When `include_deleted` is `True`: perform the scan(s) **without** a
    `FilterExpression`, returning active and inactive records alike.
- `enrich_with_image_url` and `sort_by_expiration` are unchanged and run for both
  modes, so inactive records also get a presigned URL and the list stays sorted
  by expiration (Req 5.4).
- No change to the response shape: still a JSON array of records. Inactive
  records naturally carry their stored `deleted: true` (and `deletedAt`)
  attributes, which is exactly the signal the frontend needs (Req 5.3). Active
  records carry `deleted` absent or `false`.

**Why read from query string, not body:** `list-products` is a `GET`; the
frontend already calls it via `signedFetch(GET)`. Passing the flag as a query
parameter keeps the request idempotent and cacheable and matches REST
conventions. SigV4 signing covers the query string, so the signed request stays
valid (Req 5.5).

**IAM:** no change. The existing `list-products` role already has scan +
`s3:GetObject`/presign permissions; returning additional (inactive) rows uses the
same permissions.

### Frontend: `inventoryService` changes

`InventoryProduct` gains one optional field, and `listProducts` gains one
optional argument. Both are backward compatible.

```ts
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
  deleted?: boolean;   // NEW: present/true only for inactive records
}

// includeDeleted defaults to false → identical to today's call.
export async function listProducts(includeDeleted = false): Promise<InventoryProduct[]> {
  const base = import.meta.env.VITE_LIST_API_ENDPOINT;
  // ...existing guard...
  const url = includeDeleted
    ? `${base}/list-products?includeDeleted=true`
    : `${base}/list-products`;
  const response = await signedFetch(url, { method: 'GET' });
  // ...existing error handling + return response.json()...
}
```

The existing `InventoryDashboard` call (`listProducts()`) is unaffected because
the argument defaults to `false`.

### Frontend: `NavBar` / `App` navigation

- `AppView` becomes `'upload' | 'table' | 'inventory'`.
- `NavBar` renders a third tab **between** "Add Item" and "My Pantry":
  - Order in the DOM: Add Item → **Table** → My Pantry (Req 1.1).
  - New i18n key `navBar.table` (ES/EN) with a matching emoji/style, keeping the
    existing tab styling (`nav-bar__tab`, `--active`, `aria-current`).
- `App.tsx` adds a branch: `view === 'table'` renders `<ProductTable />` inside
  an `app-section` wrapper. The `app-main--full` width treatment (currently keyed
  to `view === 'inventory'`) is extended to also apply for `'table'`, since a
  wide table benefits from the full-width layout.

### Frontend: `ProductTable` component

New directory `frontend/src/components/ProductTable/` with:

- `ProductTable.tsx` — the component.
- `ProductTable.css` — styles (table, status labels, inactive-row treatment,
  pagination controls), following the existing BEM-ish class naming
  (`product-table__…`) used across the app.
- `pagination.ts` — a small **pure** helper module (easily unit-testable):
  computes page slicing and the position indicator from `(totalItems, pageSize,
  currentPage)`.
- `index.ts` — barrel export, matching the other components.

**State (local `useState`):**

| State                | Type                              | Purpose                                              |
|----------------------|-----------------------------------|------------------------------------------------------|
| `products`           | `InventoryProduct[]`              | Last fetched list (active-only, or incl. inactive).  |
| `loading`            | `boolean`                         | Fetch in progress (Req 8.1, 8.5).                    |
| `error`              | `string \| null`                  | Fetch error message (Req 8.2).                       |
| `showInactive`       | `boolean`                         | Inactive toggle (default `false`, Req 4.1).          |
| `statusFilter`       | `ExpirationStatus \| null`        | Active status filter (Req 3.3).                      |
| `pageSize`           | `5 \| 10 \| 20`                   | Page size (default `10`, Req 6.2).                   |
| `currentPage`        | `number` (1-based)                | Current page.                                        |
| `viewerProduct`      | `InventoryProduct \| null`        | Product whose image is open in the lightbox.         |

**Derived data (via `useMemo`):**

- `rowsWithStatus` = `products.map(p => ({ product: p, status: getExpirationStatus(p.expirationDate) }))`
  — shared classifier guarantees agreement with the cards (Req 3.1).
- `filteredRows` = apply `statusFilter` (Req 3.4, 3.5). (Active/inactive is
  already decided at fetch time by `showInactive`, so no client-side
  active/inactive filtering is needed beyond what the server returned.)
- `pageInfo` = `paginate(filteredRows.length, pageSize, currentPage)` →
  `{ startIndex, endIndex, totalPages, clampedPage }`.
- `pageRows` = `filteredRows.slice(startIndex, endIndex)`.

**Row numbering:** the `#` column shows `startIndex + i + 1`, i.e. the 1-based
position within the full filtered set, continuing across pages (Req 2.3).

**Effects & handlers:**

- On mount and whenever `showInactive` changes → `fetchProducts(showInactive)`:
  set `loading`, call `listProducts(showInactive)`, store result, clear error;
  on failure set `error` (Req 8.1, 8.2, 8.5). Changing `showInactive` also resets
  `currentPage = 1` (Req 4.6).
- Changing `statusFilter` resets `currentPage = 1` (Req 3.6).
- Changing `pageSize` resets `currentPage = 1` (Req 6.7).
- Prev/next handlers clamp within `[1, totalPages]` and are disabled at the
  bounds (Req 6.8).
- If the current page ends up beyond `totalPages` after a filter change,
  `paginate` clamps it so the user never lands on an empty page past the end
  (defensive; combined with the resets above).

**Rendering states:**

- `loading` → spinner + `t('productTable.loading')` (reuse `.spinner`).
- `error` → message + retry button calling `fetchProducts(showInactive)`
  (Req 8.2).
- Loaded but `filteredRows.length === 0` → empty-state message
  (`t('productTable.empty')`), no table body, no pagination navigation (Req 6.9,
  8.3).
- Loaded with rows → controls bar (status filter + inactive toggle + page-size
  selector) + `<table>` + pagination controls + position indicator.

**Table markup (accessibility, Req 2.9):**

```tsx
<table className="product-table">
  <thead>
    <tr>
      <th scope="col">#</th>
      <th scope="col">{t('productTable.colExpires')}</th>
      <th scope="col">{t('productTable.colName')}</th>
      <th scope="col">{t('productTable.colBrand')}</th>
      <th scope="col">{t('productTable.colPresentation')}</th>
      <th scope="col">{t('productTable.colQuantity')}</th>
      <th scope="col">{t('productTable.colStatus')}</th>
      <th scope="col">{t('productTable.colActive')}</th>
      <th scope="col">{t('productTable.colImage')}</th>
    </tr>
  </thead>
  <tbody>{/* one <tr> per pageRows entry */}</tbody>
</table>
```

Per-cell rules:
- Name: `product.productName || t('productTable.unnamedProduct')` (Req 2.4).
- Expires: `product.expirationDate || t('productTable.noDate')` (Req 2.5).
- Presentation: `product.presentation` verbatim (Req 2.6).
- Quantity: `${product.quantity} ${product.unit}` (Req 2.7).
- Status: a text label/badge (`t('productTable.status<Expired|ExpiringSoon|Good>')`),
  color reinforced with the label text so status is not color-only (Req 2.2, 3.2).
- Active: `t('productTable.active')` or `t('productTable.inactive')` based on
  `product.deleted === true` (Req 4.5). Inactive rows also get a
  `product-table__row--inactive` class (dimmed) plus the "Inactive" text badge —
  not color-only (Req 4.4).
- Image: see `ImageViewer` trigger below.

**Image cell (Req 7.1, 7.2, 7.5):**
- If `product.imageUrl` is a non-empty string → a `<button type="button">`
  labeled `t('productTable.viewImage')` with
  `aria-label={t('productTable.viewImageOf', { name })}`; on click sets
  `viewerProduct = product`.
- Else (no `imageKey` / null `imageUrl`) → static text
  `t('productTable.noImage')`, no button (does not open an empty viewer).

### Frontend: `ImageViewer` component

New `frontend/src/components/ImageViewer/` (`ImageViewer.tsx`, `.css`,
`index.ts`). A focus-trapped modal lightbox, mirroring the accessibility approach
already used by `DeleteConfirmation`.

Props: `{ product: InventoryProduct; onClose: () => void }`.

Behavior:
- Renders `role="dialog"`, `aria-modal="true"`, `aria-label` referencing the
  product name (Req 7.7).
- On open: move focus into the dialog (the close button). Trap Tab focus within
  the dialog. `Esc` and a visible close button both close it (Req 7.7). On close,
  focus returns to the triggering "View" button — implemented by the parent
  `ProductTable` restoring focus to the button ref that opened the viewer
  (Req 7.8).
- Image loading (Req 7.4, 7.6): internal `status: 'loading' | 'loaded' | 'error'`.
  - Initial `loading` → spinner (`t('productTable.imageLoading')`).
  - `<img src={product.imageUrl} onLoad={→loaded} onError={→error} />`.
  - `error` → fallback message `t('productTable.imageError')` instead of a broken
    image icon.

Because `list-products` already provides the presigned `imageUrl`, the viewer
does **not** perform its own presign/network call; the "loading" state covers the
browser fetching the image bytes from S3 (Req 7.4).

### i18n additions

New `productTable` section in `frontend/src/i18n/translations.ts` (both `en` and
`es`), plus `navBar.table`. Keys (values authored in the file with real UTF-8
accents/emojis — see the encoding note in Testing/Implementation):

- `navBar.table`
- `productTable`: `loading`, `retry`, `error`, `empty`,
  `colExpires`, `colName`, `colBrand`, `colPresentation`, `colQuantity`,
  `colStatus`, `colActive`, `colImage`,
  `statusExpired`, `statusExpiringSoon`, `statusGood`,
  `filterAll`, `filterExpired`, `filterExpiringSoon`, `filterGood`,
  `active`, `inactive`, `showInactive`,
  `unnamedProduct`, `noDate`, `noImage`, `viewImage`, `viewImageOf`,
  `imageLoading`, `imageError`,
  `pageSizeLabel`, `previous`, `next`,
  `positionIndicator` (e.g. `"Showing {start}-{end} of {total}"` /
  `"Mostrando {start}-{end} de {total}"`).

The `t()` helper already supports `{token}` interpolation, so
`positionIndicator` and `viewImageOf` use it directly.

## Data Models

### InventoryProduct (frontend type)

Unchanged except for the new optional `deleted?: boolean`. When the table is
fetched **without** `includeDeleted`, every returned record has `deleted` absent
or `false`; when fetched **with** `includeDeleted=true`, inactive records carry
`deleted: true`.

### Pagination model (`pagination.ts`)

```ts
export interface PageInfo {
  clampedPage: number;   // currentPage clamped into [1, totalPages] (or 1 if empty)
  totalPages: number;    // ceil(totalItems / pageSize), min 1
  startIndex: number;    // 0-based slice start
  endIndex: number;      // 0-based slice end (exclusive)
  startLabel: number;    // 1-based first row shown (0 when empty)
  endLabel: number;      // 1-based last row shown (0 when empty)
}

export function paginate(totalItems: number, pageSize: number, currentPage: number): PageInfo;
```

`paginate` is pure and deterministic: it clamps the page, computes slice bounds,
and derives the position-indicator labels. Empty sets yield
`startLabel = endLabel = 0`, which the UI branch replaces with the empty-state
message rather than a "Showing 0-0 of 0" string.

### No DynamoDB / infrastructure model change

The `pantryvision-products` table and its CloudFormation template are unchanged.
`deleted`/`deletedAt` already exist as optional attributes (introduced by the
`manage-products` soft-delete feature). This feature only changes whether
`list-products` **filters** on `deleted`, not the data itself.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all
valid executions of a system — a formal statement about what the system should
do, bridging the human-readable spec and machine-verifiable guarantees.*

The properties below target the **pure, input-driven logic**: the `list-products`
filter selection and the client-side pagination math. UI concerns (focus trap,
rendering, i18n wiring) are covered by example/component tests (see Testing
Strategy).

### Property 1: Pagination shows at most one page worth of rows and covers the set exactly once

*For any* non-negative `totalItems`, any `pageSize ∈ {5,10,20}`, and any
`currentPage`, `paginate` yields `0 ≤ endIndex - startIndex ≤ pageSize`, and
iterating every valid page from 1 to `totalPages` produces slice ranges that
partition `[0, totalItems)` contiguously with no gaps or overlaps.

**Validates: Requirements 6.1, 6.3, 6.5**

### Property 2: Page clamping never yields an out-of-range or empty-past-the-end page

*For any* inputs, `paginate` returns `1 ≤ clampedPage ≤ totalPages` and
`totalPages ≥ 1`; when `totalItems = 0`, `startLabel = endLabel = 0` and
`totalPages = 1`; and `startIndex` is always `< totalItems` whenever
`totalItems > 0`.

**Validates: Requirements 6.8, 6.9**

### Property 3: Position indicator labels are consistent with the slice

*For any* inputs with `totalItems > 0`, the reported `startLabel` equals
`startIndex + 1`, `endLabel` equals `endIndex` (1-based inclusive), and
`1 ≤ startLabel ≤ endLabel ≤ totalItems`.

**Validates: Requirement 6.5**

### Property 4: list-products includes inactive records only when includeDeleted is truthy

*For any* set of records (mixing `deleted` true / false / absent) and *any*
`includeDeleted` query value, `list-products` returns **all** records when the
value is a case-insensitive `"true"`, and returns exactly the records whose
`deleted` is absent or `false` for every other value (including missing/empty).

**Validates: Requirements 5.1, 5.2, 5.3, 5.6**

### Property 5: Status filtering is a subset that preserves classification

*For any* fetched list and any active `statusFilter`, the displayed (pre-page)
rows are exactly the subset of rows whose `getExpirationStatus` equals the
filter; with no filter the displayed set equals the full fetched set. Filtering
never changes a row's computed status.

**Validates: Requirements 3.1, 3.4, 3.5**

## Error Handling

- **Inventory fetch failure (Req 8.2, 8.5):** `listProducts` throwing (network,
  non-2xx, or `ListProductsError`) sets `error`; the table shows the message and
  a retry button that re-invokes `fetchProducts(showInactive)`. Toggling
  "Show inactive" that triggers a failing request is handled identically.
- **Empty results (Req 8.3, 6.9):** an empty filtered set renders the
  empty-state message and suppresses pagination navigation.
- **Image load failure / expired presigned URL (Req 7.6):** the `ImageViewer`
  `onError` path shows a fallback message; the table itself is unaffected. No
  broken-image icon is shown.
- **Missing image (Req 7.5):** rows with no `imageUrl` show a "no image" label
  and never open the viewer.
- **Backend (Req 5):** the `list-products` change adds no new failure modes;
  existing `ClientError`/`Exception` handling (500 `INTERNAL_ERROR`, no PII in
  logs) is preserved. The `includeDeleted` parse is total (any non-"true" value
  → `False`), so a malformed parameter cannot error — it simply falls back to the
  default (active-only) behavior.

## Testing Strategy

Property-based testing **is applicable** to the two pure pieces: the pagination
math (frontend) and the filter-selection logic (backend). Everything else
(component rendering, focus management, navigation wiring, i18n) uses
example/component tests, consistent with the project's existing test suites
(Vitest + Testing Library on the frontend, pytest + Hypothesis + moto on the
backend).

### Backend tests (pytest + Hypothesis + moto), `backend/list-products/tests/`

- **Property 4** → a Hypothesis test generating a random mix of records with
  `deleted` set to `true` / `false` / absent, and a random `includeDeleted` query
  value drawn from `{"true","True","TRUE","false","", missing, "yes", "1"}`;
  assert the returned set equals **all** records iff the value lowercases to
  `"true"`, else the active-only set. Min **100 iterations**
  (`@settings(max_examples=100)`), tagged
  `# Feature: product-table-view, Property 4: {property_text}`.
- **Example tests:**
  - `includeDeleted=true` returns active + inactive; default returns active only
    (Req 5.1, 5.2).
  - Inactive records in the `includeDeleted=true` response carry `deleted: true`
    (Req 5.3).
  - Returned records (both modes) still have a presigned `imageUrl` and remain
    sorted by expiration (Req 5.4).
  - `queryStringParameters is None` (no query string) behaves as default
    active-only (Req 5.6) — the existing dashboard call path.
  - No PII/credentials added to logs by the change.

### Frontend tests (Vitest + Testing Library)

- **Pagination properties (1, 2, 3)** → property tests over `paginate` using
  `fast-check` (if already a dependency) or a bounded loop of randomized inputs
  otherwise; min 100 iterations; tagged with the property text. Assert the
  partition/clamp/label invariants above.
- **`ProductTable` component tests:**
  - Renders one row per product with the nine columns and correct cell values,
    including unnamed-product and no-date placeholders (Req 2.2–2.7).
  - Row numbering continues across pages (Req 2.3): with 12 items and pageSize 5,
    page 2 starts at "6".
  - Status filter narrows rows and resets to page 1 (Req 3.5, 3.6).
  - Page-size change resets to page 1 and changes rows-per-page (Req 6.3, 6.7).
  - Prev disabled on first page, next disabled on last page (Req 6.8).
  - Position indicator text matches "Showing X-Y of Z" (Req 6.5).
  - Empty state shows message, no table body (Req 8.3, 6.9).
  - Loading and error+retry states (Req 8.1, 8.2).
  - "Show inactive" checked triggers a `listProducts(true)` call, renders
    inactive rows with the inactive styling/badge and "Inactive" label, and
    resets to page 1 (Req 4.1–4.6). Mock `inventoryService.listProducts`.
- **`ImageViewer` component tests:**
  - View button has an accessible name identifying the product (Req 7.2).
  - Clicking View opens the dialog with the image; no button when no image, and a
    "no image" label instead (Req 7.1, 7.3, 7.5).
  - Loading state shown before load; `onError` shows the fallback (Req 7.4, 7.6).
  - Dialog is `role="dialog"`/`aria-modal`, focus moves in, `Esc` closes, focus
    returns to the triggering button (Req 7.7, 7.8).
- **`NavBar`/`App` tests:**
  - The Table tab renders between "Add Item" and "My Pantry" (Req 1.1) and
    selecting it shows the table and marks the tab active (Req 1.2).

### Encoding note (implementation constraint)

`translations.ts` and any file containing Spanish accents or emojis MUST be
written as **real UTF-8** (no mojibake). Per the project's tooling history, use
the editor/file-writing tools rather than PowerShell `Set-Content` for these
files, and verify a couple of accented strings after writing.

## Deployment / Infrastructure Notes

- **Only `list-products` changes.** After merging, the `list-products` Lambda
  must be **re-deployed** for `includeDeleted` to take effect. No CloudFormation
  template change is required (no new resources, env vars, or IAM). The frontend
  is deployed via Amplify Hosting as usual.
- **Env vars:** no new frontend env var — the table reuses
  `VITE_LIST_API_ENDPOINT`.
- Deploy and any push to GitHub follow the project rule: **new branch → PR →
  merge**, and require explicit confirmation before pushing or deploying.

## Future Considerations

Carried over from requirements: column sorting, server-side pagination (if the
inventory outgrows a single full fetch), a "restore" action for inactive
products, inline/bulk editing, and column selection/CSV export. Additionally, a
per-click presign refresh could replace the graceful image-expiry fallback if
long-lived table sessions with image viewing become common.
