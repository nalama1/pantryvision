/**
 * Pure pagination math for the ProductTable.
 *
 * Kept free of React and side effects so it can be property-tested in isolation:
 * given a total count, a page size, and a requested page, it clamps the page
 * into range and derives the slice bounds plus 1-based labels for the position
 * indicator ("Showing {start}-{end} of {total}").
 */

export interface PageInfo {
  /** currentPage clamped into [1, totalPages] (always 1 when the set is empty). */
  clampedPage: number;
  /** Total number of pages; at least 1 even when there are no items. */
  totalPages: number;
  /** 0-based slice start (inclusive) for Array.prototype.slice. */
  startIndex: number;
  /** 0-based slice end (exclusive) for Array.prototype.slice. */
  endIndex: number;
  /** 1-based index of the first row shown (0 when the set is empty). */
  startLabel: number;
  /** 1-based index of the last row shown (0 when the set is empty). */
  endLabel: number;
}

/**
 * Computes pagination bounds for a filtered result set.
 *
 * @param totalItems - Number of items in the (already filtered) set; clamped to >= 0.
 * @param pageSize - Rows per page; expected to be one of 5 / 10 / 20 (must be > 0).
 * @param currentPage - Requested 1-based page; clamped into [1, totalPages].
 */
export function paginate(totalItems: number, pageSize: number, currentPage: number): PageInfo {
  const safeTotal = Math.max(0, Math.floor(totalItems));
  // Guard against a non-positive page size so we never divide by zero.
  const safePageSize = Math.max(1, Math.floor(pageSize));

  // At least one page always exists, so the UI can render an empty-state page 1
  // rather than "page 0 of 0".
  const totalPages = Math.max(1, Math.ceil(safeTotal / safePageSize));
  const clampedPage = Math.min(Math.max(1, Math.floor(currentPage)), totalPages);

  if (safeTotal === 0) {
    return {
      clampedPage: 1,
      totalPages,
      startIndex: 0,
      endIndex: 0,
      startLabel: 0,
      endLabel: 0,
    };
  }

  const startIndex = (clampedPage - 1) * safePageSize;
  const endIndex = Math.min(startIndex + safePageSize, safeTotal);

  return {
    clampedPage,
    totalPages,
    startIndex,
    endIndex,
    startLabel: startIndex + 1,
    endLabel: endIndex,
  };
}
