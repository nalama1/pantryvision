# Requirements Document

## Introduction

This feature adds a spreadsheet-style table view of the product inventory to
PantryVision, complementing the existing card-based Inventory_Dashboard. The new
view is a dense, scannable list where each row is one product and each column is
one attribute, suited for users who want to review many products at a glance
rather than browse cards.

The Table_View is exposed as a new top-level navigation tab placed **before**
the existing "My Pantry" (inventory) tab. It reuses the existing data source
(the list-products endpoint) and the existing expiration-status classification
logic, so it stays consistent with the cards.

The view introduces four capabilities on top of a plain table:

1. **Active/Inactive visibility** — by default the table shows only active
   products (matching today's behavior). An "Show inactive" checkbox lets the
   user also see logically-deleted (soft-deleted) products, visually
   distinguished. This requires a backend change: the existing list-products
   Lambda filters out soft-deleted records and never returns them, so an
   opt-in `includeDeleted` parameter must be added.
2. **Status filter** — a filter over the expiration status (expired / expiring
   soon / good) consistent with the card dashboard.
3. **Pagination** — a page-size selector (5 / 10 / 20), navigation controls, and
   a position indicator, so the table scales to hundreds of products.
4. **Image column** — instead of rendering thumbnails inline, each row offers a
   "View" action that opens the product image in a modal/lightbox, with a
   loading state while the presigned S3 URL resolves and a fallback when the
   product has no image.

Final proposed columns: **# (row index) · Expires · Name · Brand · Presentation ·
Qty · Status · Active · Image**.

Two product-owner decisions were confirmed before writing this document:
- **Active/Inactive (decision 1A):** the backend WILL gain an opt-in
  `includeDeleted` parameter on list-products so inactive products can be shown.
- **Presentation (decision 2A):** the Presentation column shows the existing
  free-text `presentation` value as-is (e.g. "1 L", "500g"); no numeric grams
  field is introduced.

## Glossary

- **Table_View**: The new React component that renders the product inventory as a spreadsheet-style table (one Product_Row per product), hosting the Status_Filter, Inactive_Toggle, Pagination_Controls, and Image_Viewer.
- **Inventory_Dashboard**: The existing React component that renders saved products as cards ("My Pantry").
- **Frontend_App**: The React single-page application that hosts the navigation and switches between views.
- **Nav_Bar**: The existing React navigation component that renders the top-level view tabs.
- **List_Products_Lambda**: The existing AWS Lambda function (`list-products`) that scans the Products_Table, enriches each record with a presigned Product_Image URL, and returns the inventory.
- **Products_Table**: The existing Amazon DynamoDB table (`pantryvision-products`) storing product inventory records.
- **Product_Images_Bucket**: The existing private Amazon S3 bucket (`pantryvision-product-images`) storing uploaded product photos.
- **Product_Image**: The S3 object identified by a Product_Record's imageKey, accessed only via a short-lived presigned URL.
- **Product_Record**: A DynamoDB item containing: productId, productName, brand, presentation, expirationDate, imageKey, createdAt, quantity, unit, and the optional soft-delete attributes (`deleted`, `deletedAt`).
- **Active_Product**: A Product_Record whose `deleted` attribute is absent or false.
- **Inactive_Product**: A Product_Record whose `deleted` attribute is true (soft-deleted / logically deleted).
- **Product_Row**: A single row in the Table_View representing one Product_Record.
- **Expiration_Status**: The classification of a product's expiration urgency — `expired`, `expiring-soon`, or `normal` — computed by the existing `getExpirationStatus` logic (expiring-soon threshold = 7 days).
- **Status_Filter**: The Table_View control that limits visible rows to a single Expiration_Status (expired / expiring soon / good), or shows all statuses when no filter is active.
- **Inactive_Toggle**: The "Show inactive" checkbox in the Table_View that controls whether Inactive_Products are included in the table.
- **Pagination_Controls**: The Table_View controls for page size (5 / 10 / 20), page navigation (previous / next or page numbers), and the position indicator (e.g. "Showing 1-10 of 234").
- **Page_Size**: The number of Product_Rows shown per page; one of 5, 10, or 20.
- **Image_Viewer**: The modal/lightbox overlay that displays a single Product_Image at a larger size without leaving the Table_View.
- **View_Action**: The per-row control ("View") that opens the Image_Viewer for that product's Product_Image.
- **Include_Deleted_Param**: The opt-in query parameter (`includeDeleted=true`) that instructs the List_Products_Lambda to also return Inactive_Products.

## Requirements

### Requirement 1: Table View Navigation Entry

**User Story:** As a household manager, I want a dedicated table view I can reach from the top navigation, so that I can review my whole inventory in a compact spreadsheet-style list.

#### Acceptance Criteria

1. THE Nav_Bar SHALL display a navigation tab for the Table_View positioned before the "My Pantry" (inventory) tab.
2. WHEN the user activates the Table_View tab, THE Frontend_App SHALL display the Table_View and mark that tab as the active navigation entry.
3. THE Table_View tab label SHALL be provided through the existing i18n mechanism with both Spanish and English translations, consistent with the other Nav_Bar tabs.
4. WHEN the Table_View is the active view, THE Frontend_App SHALL continue to render the existing Upload and "My Pantry" tabs so the user can switch between all views without losing access to any of them.

### Requirement 2: Render the Inventory as a Table

**User Story:** As a household manager, I want each product shown as a row with clear columns, so that I can compare products quickly.

#### Acceptance Criteria

1. WHEN the Table_View loads the inventory, THE Table_View SHALL render one Product_Row per returned Product_Record within the current page.
2. THE Table_View SHALL present, for each Product_Row, the following columns in order: a row-number index, expiration date, product name, brand, presentation, quantity, Expiration_Status, active/inactive state, and an image View_Action.
3. THE row-number index column SHALL display the position of the row within the full filtered result set (1-based), such that the first row of page 1 is number 1 and numbering continues across pages according to the current Page_Size and page.
4. WHERE a Product_Record has an empty product name, THE Table_View SHALL render an accessible placeholder label rather than a blank cell.
5. WHERE a Product_Record has an empty expirationDate, THE Table_View SHALL render a neutral placeholder in the expiration date cell and classify its Expiration_Status as `normal`.
6. THE Table_View SHALL display the presentation column using the Product_Record's free-text `presentation` value exactly as stored, without transformation.
7. THE Table_View SHALL display the quantity column using the Product_Record's `quantity` and `unit` values.
8. THE column headers SHALL be provided through the existing i18n mechanism with both Spanish and English translations.
9. THE table SHALL use semantic table markup with column headers associated with their cells so it is navigable by assistive technologies.

### Requirement 3: Expiration Status Column and Filter

**User Story:** As a household manager, I want to see and filter by whether a product is expired, expiring soon, or good, so that I can focus on the products that need attention.

#### Acceptance Criteria

1. THE Table_View SHALL compute each Product_Row's Expiration_Status using the same classification logic used by the Inventory_Dashboard (`getExpirationStatus`), so the two views agree on status.
2. THE Table_View SHALL visually indicate each Product_Row's Expiration_Status (expired / expiring soon / good) in a way that does not rely on color alone (for example, a text label or badge).
3. THE Table_View SHALL provide a Status_Filter that lets the user restrict visible rows to a single Expiration_Status: expired, expiring soon, or good.
4. WHEN no Status_Filter is active, THE Table_View SHALL include Product_Rows of every Expiration_Status.
5. WHEN a Status_Filter is active, THE Table_View SHALL display only the Product_Rows whose Expiration_Status matches the selected filter.
6. WHEN the active Status_Filter changes, THE Table_View SHALL reset pagination to the first page.
7. THE Status_Filter labels SHALL be provided through the existing i18n mechanism with both Spanish and English translations.

### Requirement 4: Show Inactive (Soft-Deleted) Products

**User Story:** As a household manager, I want to optionally see products I previously deleted, so that I can review or account for them without them cluttering my normal view.

#### Acceptance Criteria

1. THE Table_View SHALL provide an Inactive_Toggle labeled to indicate it shows inactive products, unchecked by default.
2. WHILE the Inactive_Toggle is unchecked, THE Table_View SHALL display only Active_Products, matching the current default inventory behavior.
3. WHEN the Inactive_Toggle is checked, THE Table_View SHALL request the inventory including Inactive_Products and display both Active_Products and Inactive_Products.
4. WHEN the Table_View displays an Inactive_Product, THE Table_View SHALL visually distinguish that Product_Row from Active_Products (for example, a dimmed/muted row style and/or an "Inactive" badge) in a way that does not rely on color alone.
5. THE active/inactive column SHALL indicate, per Product_Row, whether the product is active or inactive using a text label, provided through the existing i18n mechanism with Spanish and English translations.
6. WHEN the Inactive_Toggle state changes, THE Table_View SHALL reset pagination to the first page.
7. THE Inactive_Toggle label SHALL be provided through the existing i18n mechanism with both Spanish and English translations.

### Requirement 5: List-Products Support for Including Inactive Products

**User Story:** As a developer, I want the list-products endpoint to optionally return soft-deleted products, so that the table view can show inactive products on demand without changing the default behavior of other views.

#### Acceptance Criteria

1. WHEN the List_Products_Lambda receives a request without the Include_Deleted_Param, or with the Include_Deleted_Param set to any value other than a case-insensitive "true", THE List_Products_Lambda SHALL exclude every Inactive_Product from the response, preserving today's default behavior.
2. WHEN the List_Products_Lambda receives a request with the Include_Deleted_Param equal to a case-insensitive "true", THE List_Products_Lambda SHALL include both Active_Products and Inactive_Products in the response.
3. WHEN the List_Products_Lambda returns an Inactive_Product, THE returned record SHALL carry an indication of its inactive state (its `deleted` attribute set to true) so the Table_View can distinguish it.
4. THE List_Products_Lambda SHALL continue to enrich each returned Product_Record with a presigned Product_Image URL and to sort results by expiration date, regardless of whether Inactive_Products are included.
5. THE List_Products_Lambda SHALL read the Include_Deleted_Param from the request query string parameters.
6. THE change to the List_Products_Lambda SHALL NOT require any data migration and SHALL remain backward compatible with existing callers that do not send the Include_Deleted_Param (such as the Inventory_Dashboard).

Note: This requirement modifies the EXISTING List_Products_Lambda. The design and tasks phases MUST account for updating the existing Lambda (and re-deploying it) rather than only adding frontend code.

### Requirement 6: Pagination

**User Story:** As a household manager with many products, I want the table paginated with a selectable page size, so that large inventories stay readable and fast.

#### Acceptance Criteria

1. THE Pagination_Controls SHALL offer a Page_Size selector with the options 5, 10, and 20 records per page.
2. THE Table_View SHALL default to a Page_Size of 10 records per page.
3. THE Table_View SHALL display at most Page_Size Product_Rows on a single page.
4. THE Pagination_Controls SHALL provide a way to navigate to the previous page and to the next page (or select a page number).
5. THE Pagination_Controls SHALL display a position indicator showing the range of rows currently displayed and the total number of rows in the filtered result set (for example, "Showing 1-10 of 234").
6. THE position indicator and the row totals SHALL reflect the current combination of Status_Filter and Inactive_Toggle (i.e., they count only the rows that pass the active filters).
7. WHEN the user changes the Page_Size, THE Table_View SHALL reset pagination to the first page.
8. WHILE the user is on the first page, THE Pagination_Controls SHALL prevent navigating to a previous page; WHILE the user is on the last page, THE Pagination_Controls SHALL prevent navigating to a next page.
9. WHEN the filtered result set is empty, THE Table_View SHALL display an empty-state message (via the existing i18n mechanism) instead of an empty table body, and SHALL NOT offer navigation to a non-existent page.
10. THE Pagination_Controls labels and the position indicator text SHALL be provided through the existing i18n mechanism with both Spanish and English translations.

### Requirement 7: Image Column with Viewer

**User Story:** As a household manager, I want to open a product's photo on demand from the table, so that the table stays compact but I can still see the image when I need it.

#### Acceptance Criteria

1. THE Table_View SHALL render, in each Product_Row's image column, a View_Action control instead of an inline thumbnail.
2. THE View_Action control SHALL be reachable by keyboard focus and have an accessible name that identifies which product's image it opens.
3. WHEN the user activates the View_Action for a Product_Row, THE Table_View SHALL open the Image_Viewer displaying that product's Product_Image without navigating away from the Table_View.
4. WHILE the presigned Product_Image URL is being resolved or the image is loading, THE Image_Viewer SHALL display a loading indicator.
5. WHERE a Product_Record has no associated Product_Image (empty imageKey or null image URL), THE Table_View SHALL indicate in the image column that no image is available and SHALL NOT open an empty Image_Viewer.
6. IF the Product_Image fails to load in the Image_Viewer, THEN THE Image_Viewer SHALL display a fallback message indicating the image could not be shown, rather than a broken image.
7. WHILE the Image_Viewer is open, THE Frontend_App SHALL expose it to assistive technologies as a modal dialog, move keyboard focus into it, confine focus to it, and provide a keyboard-accessible way to close it.
8. WHEN the user closes the Image_Viewer, THE Frontend_App SHALL return keyboard focus to the View_Action control that opened it.

### Requirement 8: Loading, Error, and Empty States

**User Story:** As a household manager, I want clear feedback while the table loads or if something goes wrong, so that I understand the state of my inventory view.

#### Acceptance Criteria

1. WHILE the Table_View is retrieving the inventory, THE Table_View SHALL display a loading indicator.
2. IF retrieving the inventory fails, THEN THE Table_View SHALL display an error message and offer a way to retry the request.
3. WHEN retrieving the inventory succeeds but returns no products for the active filters, THE Table_View SHALL display an empty-state message.
4. THE loading, error, and empty-state messages SHALL be provided through the existing i18n mechanism with both Spanish and English translations.
5. WHEN the user toggles the Inactive_Toggle in a way that requires a different inventory request, THE Table_View SHALL show a loading indication for that request and SHALL handle its failure per criterion 2.

## Future Considerations

- **Column sorting**: Letting the user sort by clicking column headers (name, expiration, quantity) is out of scope for this iteration and could be added later.
- **Server-side pagination**: This feature paginates client-side after fetching the inventory, which is adequate for the expected scale (hundreds of products). If the inventory grows to the point where fetching all records is too costly, a future iteration could move pagination (and filtering) to the backend.
- **Restore inactive products**: Showing inactive products is read-only here. A future iteration could add a "restore" action to reactivate a soft-deleted product from the table, building on the manage-products soft-delete model.
- **Inline editing / bulk actions**: Editing cells directly in the table or selecting multiple rows for bulk operations is out of scope and could be considered later.
- **Column selection / export**: Choosing which columns to show or exporting the table (CSV) is out of scope for this iteration.
