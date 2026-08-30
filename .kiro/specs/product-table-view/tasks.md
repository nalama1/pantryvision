# Implementation Plan: Product Table View

## Overview

Add a spreadsheet-style table view of the inventory, reachable from a new
`NavBar` tab placed **before** "My Pantry". The work is frontend-heavy with one
small, backward-compatible backend change: `list-products` gains an optional
`includeDeleted` query parameter so inactive (soft-deleted) products can be shown
on demand. Pagination and status filtering are client-side; the image column uses
a "View" action that opens a focus-trapped lightbox showing the presigned URL
that `list-products` already returns.

Conventions to follow throughout:

- **Reuse, don't duplicate:** the table computes expiration status with the
  existing `getExpirationStatus` (shared with `InventoryDashboard`), calls the
  existing `list-products` endpoint through `signedFetch`, and uses the existing
  i18n `t()` mechanism. No new endpoint, no new infrastructure, no new env var.
- **Backward compatible backend:** `includeDeleted` is opt-in. A request with no
  parameter (the `InventoryDashboard`'s existing call) behaves exactly as today.
  No data migration; no CloudFormation change. The `list-products` Lambda must be
  **re-deployed** for the new parameter to take effect.
- **Accessibility:** semantic `<table>` markup with `<th scope="col">`, status
  conveyed by text (not color alone), keyboard-operable "View" buttons, and a
  `role="dialog"` / `aria-modal` lightbox with focus trap and focus restore,
  mirroring the existing `DeleteConfirmation` pattern.
- **Client-side pagination:** page size 5 / 10 / 20 (default 10) computed by a
  pure `pagination.ts` helper; changing the status filter, the "Show inactive"
  toggle, or the page size resets to page 1.
- **Encoding:** files with Spanish accents/emojis (especially `translations.ts`)
  MUST be written as real UTF-8 using the editor/file tools, NOT PowerShell
  `Set-Content`. Verify a couple of accented strings after writing.
- Backend tests use pytest + Hypothesis (100+ iterations) with moto/stubbed
  DynamoDB. Frontend tests use Vitest + Testing Library (property tests over the
  pure pagination helper).

## Tasks

- [ ] 1. Backend: add `includeDeleted` support to `list-products`
  - [ ] 1.1 Modify `list-products` to read the query param and conditionally skip the filter (`backend/list-products/handler.py`)
    - Add a total, defensive helper `_wants_deleted(event) -> bool` that reads
      `event.get("queryStringParameters") or {}` (API Gateway sends `None` when no
      query string is present), takes `includeDeleted`, and returns
      `str(value).strip().lower() == "true"` (any other value → `False`)
    - Change `scan_all_products(include_deleted: bool = False)` to apply the existing
      `FilterExpression = Attr("deleted").not_exists() | Attr("deleted").eq(False)`
      on the initial scan AND every paginated follow-up scan **only when**
      `include_deleted is False`; when `True`, scan with **no** `FilterExpression`
    - `lambda_handler` calls `_wants_deleted(event)` and passes it into
      `scan_all_products`; enrichment (`enrich_with_image_url`), sort
      (`sort_by_expiration`), and the response shape stay unchanged
    - Inactive records naturally carry their stored `deleted: true` / `deletedAt`,
      which is the signal the frontend uses; active records carry `deleted` absent/false
    - Use type hints, PEP 8, English comments explaining the "why" (opt-in, backward
      compatible, default preserves today's behavior)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 1.2 Write property test for the includeDeleted filter selection
    - **Property 4: list-products includes inactive records only when includeDeleted is truthy**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.6**
    - Hypothesis: generate a random mix of records with `deleted` true/false/absent
      and a random query value from `{"true","True","TRUE","false","","yes","1", missing}`;
      assert the returned set equals ALL records iff the value lowercases to `"true"`,
      else the active-only set. `@settings(max_examples=100)`, tagged
      `# Feature: product-table-view, Property 4: {property_text}`
    - moto/stubbed DynamoDB; place in `backend/list-products/tests/`

  - [ ]* 1.3 Write unit tests for list-products includeDeleted edge cases
    - `includeDeleted=true` returns active + inactive; default (no param) returns
      active-only (Req 5.1, 5.2); inactive records in the `true` response carry
      `deleted: true` (Req 5.3); returned records still have a presigned `imageUrl`
      and remain sorted by expiration in both modes (Req 5.4); `queryStringParameters
      is None` behaves as default active-only (Req 5.6)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

- [ ] 2. Frontend service: optional includeDeleted on `listProducts`
  - [ ] 2.1 Extend `inventoryService.ts` (`frontend/src/services/inventoryService.ts`)
    - Add optional `deleted?: boolean` to the `InventoryProduct` interface
    - Change `listProducts(includeDeleted = false)` to build the URL as
      `${base}/list-products?includeDeleted=true` when `includeDeleted` is true, else
      the existing `${base}/list-products`; keep the env-var guard, error handling,
      and return type unchanged
    - The default `false` keeps the existing `InventoryDashboard` call
      (`listProducts()`) byte-for-byte compatible
    - _Requirements: 4.3, 5.5_

  - [ ]* 2.2 Write service tests for the includeDeleted argument
    - Mock `signedFetch`; assert `listProducts()` calls `/list-products` (no query)
      and `listProducts(true)` calls `/list-products?includeDeleted=true`; assert the
      parsed array is returned and errors still raise `ListProductsError`
    - _Requirements: 4.3, 5.5_

- [ ] 3. Frontend: pure pagination helper
  - [ ] 3.1 Create `pagination.ts` (`frontend/src/components/ProductTable/pagination.ts`)
    - Export `PageInfo` and `paginate(totalItems, pageSize, currentPage): PageInfo`
      as designed: clamp `currentPage` into `[1, totalPages]`, `totalPages =
      max(1, ceil(totalItems/pageSize))`, compute `startIndex`/`endIndex` (exclusive),
      and 1-based `startLabel`/`endLabel` (both 0 when `totalItems === 0`)
    - Pure and deterministic (no React, no side effects) so it is trivially testable
    - _Requirements: 6.1, 6.3, 6.5, 6.8, 6.9_

  - [ ]* 3.2 Write property tests for `paginate`
    - **Property 1: Pagination shows at most one page worth of rows and covers the set exactly once** — Validates 6.1, 6.3, 6.5
    - **Property 2: Page clamping never yields an out-of-range or empty-past-the-end page** — Validates 6.8, 6.9
    - **Property 3: Position indicator labels are consistent with the slice** — Validates 6.5
    - Use `fast-check` if already a dependency, else a bounded randomized loop; min
      100 iterations; tag each with `// Feature: product-table-view, Property N: ...`

- [ ] 4. Frontend: i18n strings (UTF-8)
  - [ ] 4.1 Add `navBar.table` and the `productTable` section to `translations.ts`
    - Add to BOTH `en` and `es`: `navBar.table`; and a `productTable` block with
      `loading`, `retry`, `error`, `empty`, the nine column headers
      (`colExpires`, `colName`, `colBrand`, `colPresentation`, `colQuantity`,
      `colStatus`, `colActive`, `colImage`; the `#` header can be a literal),
      `statusExpired`, `statusExpiringSoon`, `statusGood`,
      `filterAll`, `filterExpired`, `filterExpiringSoon`, `filterGood`,
      `active`, `inactive`, `showInactive`, `unnamedProduct`, `noDate`, `noImage`,
      `viewImage`, `viewImageOf` ("{name}"), `imageLoading`, `imageError`,
      `pageSizeLabel`, `previous`, `next`, and
      `positionIndicator` ("Showing {start}-{end} of {total}" /
      "Mostrando {start}-{end} de {total}")
    - Spanish values warm and correct with real accents; English matches existing tone
    - **Write with the editor/file tools (real UTF-8), NOT `Set-Content`**; after
      writing, verify a couple of accented Spanish strings render correctly
    - _Requirements: 1.3, 2.8, 3.7, 4.5, 4.7, 6.10, 8.4_

- [ ] 5. Frontend: `ImageViewer` lightbox
  - [ ] 5.1 Create the `ImageViewer` component (`frontend/src/components/ImageViewer/`)
    - `ImageViewer.tsx`, `ImageViewer.css`, `index.ts`. Props
      `{ product: InventoryProduct; onClose: () => void }`
    - `role="dialog"`, `aria-modal="true"`, `aria-label` referencing the product name;
      move focus to the close button on open; trap Tab focus; close on `Esc` and on a
      visible close button (Req 7.7). Focus restore to the trigger is handled by the
      parent (see 6.1)
    - Internal `status: 'loading' | 'loaded' | 'error'`: show a spinner +
      `t('productTable.imageLoading')` until the `<img onLoad>` fires; on `<img onError>`
      show `t('productTable.imageError')` fallback (no broken-image icon). Uses
      `product.imageUrl` directly (no extra presign call) (Req 7.4, 7.6)
    - _Requirements: 7.4, 7.6, 7.7_

  - [ ]* 5.2 Write `ImageViewer` tests
    - Renders `role="dialog"` + `aria-modal`, focus moves in, `Esc` closes and fires
      `onClose` (Req 7.7); loading state shown before load; `onError` shows the
      fallback message (Req 7.4, 7.6)
    - _Requirements: 7.4, 7.6, 7.7_

- [ ] 6. Frontend: `ProductTable` component
  - [ ] 6.1 Create the `ProductTable` component (`frontend/src/components/ProductTable/`)
    - `ProductTable.tsx`, `ProductTable.css`, `index.ts`. State: `products`,
      `loading`, `error`, `showInactive` (default false), `statusFilter`
      (default null), `pageSize` (default 10), `currentPage` (default 1),
      `viewerProduct` (default null); keep a ref map of "View" buttons for focus restore
    - `fetchProducts(showInactive)` sets loading, calls
      `listProducts(showInactive)`, stores result, clears/sets error; run on mount and
      whenever `showInactive` changes (Req 8.1, 8.2, 8.5). Changing `showInactive`
      resets `currentPage = 1` (Req 4.6)
    - Derived via `useMemo`: `rowsWithStatus` using `getExpirationStatus` (Req 3.1);
      `filteredRows` applying `statusFilter` (Req 3.4, 3.5);
      `pageInfo = paginate(filteredRows.length, pageSize, currentPage)`;
      `pageRows = filteredRows.slice(startIndex, endIndex)`
    - Controls bar: status filter (all / expired / expiring-soon / good) that resets to
      page 1 (Req 3.3, 3.6); "Show inactive" checkbox unchecked by default (Req 4.1);
      page-size selector 5/10/20 that resets to page 1 (Req 6.1, 6.7)
    - Semantic table (Req 2.9): `<thead>` with `<th scope="col">` for the nine columns
      in order (#, Expires, Name, Brand, Presentation, Qty, Status, Active, Image);
      one `<tr>` per `pageRows`. Cells: row number `startIndex + i + 1` (Req 2.3);
      name or `unnamedProduct` (Req 2.4); expirationDate or `noDate` (Req 2.5);
      presentation verbatim (Req 2.6); `${quantity} ${unit}` (Req 2.7); status text
      label/badge not color-only (Req 2.2, 3.2); Active/Inactive text label from
      `product.deleted === true`, inactive rows get `product-table__row--inactive`
      (dimmed) + "Inactive" badge, not color-only (Req 4.4, 4.5)
    - Image cell: if `product.imageUrl` truthy → focusable `<button>` with
      `aria-label={t('productTable.viewImageOf',{name})}` that sets `viewerProduct`
      (Req 7.1, 7.2, 7.3); else static `t('productTable.noImage')`, no button
      (Req 7.5). On viewer close, restore focus to that row's "View" button (Req 7.8)
    - Pagination controls: previous/next disabled at bounds (Req 6.8); position
      indicator via `t('productTable.positionIndicator', {start,end,total})` reflecting
      the filtered totals (Req 6.5, 6.6)
    - States: loading spinner (Req 8.1); error message + retry calling
      `fetchProducts(showInactive)` (Req 8.2); empty filtered set → empty-state message,
      no table body, no page navigation (Req 6.9, 8.3)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.9, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 7.1, 7.2, 7.3, 7.5, 7.8, 8.1, 8.2, 8.3, 8.5_

  - [ ]* 6.2 Write `ProductTable` component tests
    - One row per product with correct cell values incl. unnamed/no-date placeholders
      (Req 2.2–2.7); row numbering continues across pages (12 items, size 5 → page 2
      starts at 6) (Req 2.3); status filter narrows rows and resets to page 1
      (Req 3.5, 3.6); page-size change resets to page 1 and changes rows/page
      (Req 6.3, 6.7); prev disabled on first page / next disabled on last (Req 6.8);
      position indicator text "Showing X-Y of Z" (Req 6.5); empty state, no body
      (Req 6.9, 8.3); loading and error+retry (Req 8.1, 8.2); "Show inactive" checked
      triggers `listProducts(true)`, renders inactive rows with badge/label + inactive
      styling and resets to page 1 (Req 4.1–4.6). Mock `inventoryService.listProducts`
    - _Requirements: 2.2, 2.3, 3.5, 3.6, 4.1, 4.4, 4.5, 4.6, 6.3, 6.5, 6.7, 6.8, 6.9, 8.1, 8.2, 8.3_

- [ ] 7. Frontend: navigation wiring
  - [ ] 7.1 Add the Table tab to `NavBar` and route it in `App`
    - `NavBar.tsx`: change `AppView` to `'upload' | 'table' | 'inventory'`; render a
      third tab **between** "Add Item" and "My Pantry" using `t('navBar.table')`,
      reusing `nav-bar__tab` styling, `--active` class, and `aria-current` (Req 1.1)
    - `App.tsx`: add a `view === 'table'` branch rendering `<ProductTable />` inside an
      `app-section`; extend the `app-main--full` width treatment to also apply when
      `view === 'table'`; keep the Upload and inventory branches intact so all three
      tabs remain reachable (Req 1.2, 1.4)
    - _Requirements: 1.1, 1.2, 1.4_

  - [ ]* 7.2 Write NavBar/App navigation tests
    - Table tab renders between "Add Item" and "My Pantry" (Req 1.1); selecting it shows
      the table and marks the tab active (`aria-current`) (Req 1.2); the other two tabs
      remain present (Req 1.4)
    - _Requirements: 1.1, 1.2, 1.4_

- [ ] 8. Register component exports
  - [ ] 8.1 Export the new components
    - Add `ProductTable` and `ImageViewer` to `frontend/src/components/index.ts`
      (and their own `index.ts` barrels) consistent with the existing components
    - _Requirements: 1.2_

- [ ] 9. Final checkpoint
  - Run the frontend test suite (Vitest) and the backend tests (pytest) for
    `list-products`; run the frontend build/typecheck. Ensure everything passes and
    ask the user if questions arise.
  - Remind the user: the `list-products` Lambda must be **re-deployed** for
    `includeDeleted` to take effect, and any push/deploy follows the project rule
    (new branch → PR → merge) with explicit confirmation.

## Notes

- Tasks marked with `*` are optional (tests) and can be skipped for a faster MVP,
  but the pagination property tests (3.2) and the backend filter test (1.2) are the
  highest-value ones given the correctness properties.
- No new infrastructure, IAM, env var, or CloudFormation change. The ONLY deploy
  artifact is the re-deployed `list-products` Lambda; the frontend ships via Amplify.
- Pagination and status filtering are client-side (adequate at hundreds of products,
  per the design's Future Considerations). Toggling "Show inactive" re-fetches; the
  status filter and pagination do not.
- The `ImageViewer` shows the presigned `imageUrl` returned by `list-products`
  (~300s TTL). Expiry is handled gracefully (fallback message), not proactively.
- Encoding: write `translations.ts` (and any accented/emoji file) as real UTF-8 with
  the editor/file tools; verify accented strings after writing.
- Each task references specific requirements for traceability; the final checkpoint
  ensures the suite passes before any deploy.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1", "4.1", "5.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.2", "3.2", "5.2", "6.1"] },
    { "id": 2, "tasks": ["6.2", "7.1", "8.1"] },
    { "id": 3, "tasks": ["7.2", "9"] }
  ]
}
```
