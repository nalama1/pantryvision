import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './ProductTable.css';
import { listProducts } from '../../services/inventoryService';
import type { InventoryProduct } from '../../services/inventoryService';
import { getExpirationStatus, type ExpirationStatus } from '../InventoryDashboard/expirationStatus';
import { useLanguage } from '../../i18n/LanguageContext';
import { ImageViewer } from '../ImageViewer';
import { paginate } from './pagination';
import { buildCsv, downloadCsv, buildExportFilename, type ExportLabels } from './exportCsv';

type PageSize = 5 | 10 | 20;
const PAGE_SIZE_OPTIONS: PageSize[] = [5, 10, 20];
const DEFAULT_PAGE_SIZE: PageSize = 10;

// Maps an expiration status to its i18n status-label key, shared by the Status
// column and the status filter so the two never drift apart.
const STATUS_LABEL_KEY: Record<ExpirationStatus, string> = {
  expired: 'productTable.statusExpired',
  'expiring-soon': 'productTable.statusExpiringSoon',
  normal: 'productTable.statusGood',
};

/**
 * ProductTable renders the inventory as a compact, accessible spreadsheet-style
 * table: one row per product, with a status filter, a "show inactive" toggle,
 * client-side pagination, and an on-demand image lightbox.
 *
 * It reuses getExpirationStatus (shared with InventoryDashboard) so both views
 * agree on status, and the same list-products endpoint via listProducts. Only
 * toggling "show inactive" triggers a re-fetch (it changes what the server
 * returns); the status filter and pagination operate on already-fetched data.
 */
export function ProductTable() {
  const { t } = useLanguage();
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [statusFilter, setStatusFilter] = useState<ExpirationStatus | null>(null);
  const [pageSize, setPageSize] = useState<PageSize>(DEFAULT_PAGE_SIZE);
  const [currentPage, setCurrentPage] = useState(1);
  const [viewerProduct, setViewerProduct] = useState<InventoryProduct | null>(null);
  // While true, the table renders every filtered row (ignoring pagination) so
  // window.print() captures the whole set, not just the current page.
  const [isPrinting, setIsPrinting] = useState(false);

  // Refs to each row's "View" button so focus can be restored to the one that
  // opened the lightbox after it closes (Req 7.8).
  const viewButtonRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const viewerOpenerRef = useRef<string | null>(null);

  const fetchProducts = useCallback(async (includeInactive: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const result = await listProducts(includeInactive);
      setProducts(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : t('productTable.error');
      setError(message || t('productTable.error'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  // Fetch on mount and whenever the inactive toggle changes (Req 4.3, 8.5). The
  // toggle also resets pagination to page 1 (Req 4.6) via handleToggleInactive.
  useEffect(() => {
    fetchProducts(showInactive);
  }, [fetchProducts, showInactive]);

  // Compute status once per product; reused for filtering and the status column.
  const rowsWithStatus = useMemo(
    () => products.map((product) => ({
      product,
      status: getExpirationStatus(product.expirationDate),
    })),
    [products],
  );

  const filteredRows = useMemo(() => {
    if (!statusFilter) return rowsWithStatus;
    return rowsWithStatus.filter(({ status }) => status === statusFilter);
  }, [rowsWithStatus, statusFilter]);

  const pageInfo = useMemo(
    () => paginate(filteredRows.length, pageSize, currentPage),
    [filteredRows.length, pageSize, currentPage],
  );

  const pageRows = useMemo(
    () => (isPrinting ? filteredRows : filteredRows.slice(pageInfo.startIndex, pageInfo.endIndex)),
    [isPrinting, filteredRows, pageInfo.startIndex, pageInfo.endIndex],
  );

  const handleToggleInactive = useCallback(() => {
    setShowInactive((prev) => !prev);
    setCurrentPage(1); // Req 4.6
  }, []);

  const handleStatusFilter = useCallback((status: ExpirationStatus | null) => {
    setStatusFilter(status);
    setCurrentPage(1); // Req 3.6
  }, []);

  const handlePageSizeChange = useCallback((size: PageSize) => {
    setPageSize(size);
    setCurrentPage(1); // Req 6.7
  }, []);

  const goToPrevious = useCallback(() => {
    setCurrentPage((page) => Math.max(1, page - 1));
  }, []);

  const goToNext = useCallback(() => {
    setCurrentPage((page) => Math.min(pageInfo.totalPages, page + 1));
  }, [pageInfo.totalPages]);

  const handleOpenViewer = useCallback((product: InventoryProduct) => {
    viewerOpenerRef.current = product.productId;
    setViewerProduct(product);
  }, []);

  const handleCloseViewer = useCallback(() => {
    const openerId = viewerOpenerRef.current;
    setViewerProduct(null);
    // Restore focus to the "View" button that opened the lightbox (Req 7.8).
    if (openerId) {
      viewButtonRefs.current.get(openerId)?.focus();
      viewerOpenerRef.current = null;
    }
  }, []);

  // Export/print operate on the full FILTERED set (respecting status filter and
  // the inactive toggle), not just the current page, so the user gets the whole
  // view they are looking at. The image column is omitted (it is an action).
  const handleExportCsv = useCallback(() => {
    const labels: ExportLabels = {
      number: '#',
      expires: t('productTable.colExpires'),
      name: t('productTable.colName'),
      brand: t('productTable.colBrand'),
      presentation: t('productTable.colPresentation'),
      quantity: t('productTable.colQuantity'),
      status: t('productTable.colStatus'),
      active: t('productTable.colActive'),
      statusExpired: t('productTable.statusExpired'),
      statusExpiringSoon: t('productTable.statusExpiringSoon'),
      statusGood: t('productTable.statusGood'),
      activeLabel: t('productTable.active'),
      inactiveLabel: t('productTable.inactive'),
      unnamedProduct: t('productTable.unnamedProduct'),
    };
    const csv = buildCsv(filteredRows, labels);
    downloadCsv(csv, buildExportFilename());
  }, [filteredRows, t]);

  const handlePrint = useCallback(() => {
    // window.print() only captures what is in the DOM, which is the current
    // page. To print the WHOLE filtered set, temporarily render every row, print,
    // then restore the previous pagination. Two rAFs ensure React has committed
    // the expanded rows to the DOM before the (blocking) print dialog opens.
    setIsPrinting(true);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        window.print();
        setIsPrinting(false);
      });
    });
  }, []);

  if (loading) {
    return (
      <div className="product-table__state" data-testid="product-table-loading">
        <div className="spinner" role="status" aria-label={t('productTable.loading')}></div>
        <p>{t('productTable.loading')}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="product-table__state" role="alert" data-testid="product-table-error">
        <p className="product-table__error-text">{error}</p>
        <button
          className="btn btn--primary"
          type="button"
          onClick={() => fetchProducts(showInactive)}
          data-testid="product-table-retry-btn"
        >
          {t('productTable.retry')}
        </button>
      </div>
    );
  }

  const statusFilterButtons: Array<{ value: ExpirationStatus | null; labelKey: string }> = [
    { value: null, labelKey: 'productTable.filterAll' },
    { value: 'expired', labelKey: 'productTable.filterExpired' },
    { value: 'expiring-soon', labelKey: 'productTable.filterExpiringSoon' },
    { value: 'normal', labelKey: 'productTable.filterGood' },
  ];

  return (
    <div data-testid="product-table">
      <div className="product-table__controls">
        <div className="product-table__filters" role="group" aria-label={t('productTable.colStatus')}>
          {statusFilterButtons.map(({ value, labelKey }) => (
            <button
              key={value ?? 'all'}
              type="button"
              className={`product-table__filter ${statusFilter === value ? 'product-table__filter--active' : ''}`}
              onClick={() => handleStatusFilter(value)}
              aria-pressed={statusFilter === value}
              data-testid={`product-table-filter-${value ?? 'all'}`}
            >
              {t(labelKey)}
            </button>
          ))}
        </div>

        <label className="product-table__inactive-toggle">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={handleToggleInactive}
            data-testid="product-table-show-inactive"
          />
          {t('productTable.showInactive')}
        </label>

        <div className="product-table__actions">
          <button
            type="button"
            className="btn btn--secondary product-table__action-btn"
            onClick={handleExportCsv}
            disabled={filteredRows.length === 0}
            data-testid="product-table-export-btn"
          >
            {t('productTable.exportExcel')}
          </button>
          <button
            type="button"
            className="btn btn--secondary product-table__action-btn"
            onClick={handlePrint}
            disabled={filteredRows.length === 0}
            data-testid="product-table-print-btn"
          >
            {t('productTable.print')}
          </button>
        </div>

        <label className="product-table__page-size">
          {t('productTable.pageSizeLabel')}
          <select
            value={pageSize}
            onChange={(e) => handlePageSizeChange(Number(e.target.value) as PageSize)}
            data-testid="product-table-page-size"
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>{size}</option>
            ))}
          </select>
        </label>
      </div>

      {filteredRows.length === 0 ? (
        <div className="product-table__state" data-testid="product-table-empty">
          <p>{t('productTable.empty')}</p>
        </div>
      ) : (
        <>
          <div className="product-table__scroll">
            <table className="product-table__table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">{t('productTable.colStatus')}</th>
                  <th scope="col">{t('productTable.colExpires')}</th>
                  <th scope="col">{t('productTable.colName')}</th>
                  <th scope="col">{t('productTable.colBrand')}</th>
                  <th scope="col">{t('productTable.colPresentation')}</th>
                  <th scope="col">{t('productTable.colQuantity')}</th>
                  <th scope="col">{t('productTable.colImage')}</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map(({ product, status }, index) => {
                  const isInactive = product.deleted === true;
                  const displayName = product.productName || t('productTable.unnamedProduct');
                  // When printing we render all rows, so number from 1; otherwise
                  // continue numbering across pages using the page's start offset.
                  const rowNumber = (isPrinting ? 0 : pageInfo.startIndex) + index + 1; // Req 2.3
                  const hasImage = Boolean(product.imageUrl);

                  return (
                    <tr
                      key={product.productId}
                      className={isInactive ? 'product-table__row--inactive' : ''}
                      data-testid="product-table-row"
                    >
                      <td>{rowNumber}</td>
                      <td>
                        <span className={`product-table__status product-table__status--${status}`}>
                          {t(STATUS_LABEL_KEY[status])}
                        </span>
                      </td>
                      <td>{product.expirationDate || t('productTable.noDate')}</td>
                      <td>
                        {displayName}
                        {isInactive && (
                          <span className="product-table__badge product-table__badge--inactive">
                            {t('productTable.inactive')}
                          </span>
                        )}
                      </td>
                      <td>{product.brand}</td>
                      <td>{product.presentation}</td>
                      <td>{product.quantity} {product.unit}</td>
                      <td>
                        {hasImage ? (
                          <button
                            type="button"
                            className="btn btn--secondary product-table__view-btn"
                            onClick={() => handleOpenViewer(product)}
                            aria-label={t('productTable.viewImageOf', { name: displayName })}
                            data-testid="product-table-view-btn"
                            ref={(el) => {
                              if (el) viewButtonRefs.current.set(product.productId, el);
                              else viewButtonRefs.current.delete(product.productId);
                            }}
                          >
                            {t('productTable.viewImage')}
                          </button>
                        ) : (
                          <span className="product-table__no-image">{t('productTable.noImage')}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="product-table__pagination">
            <span className="product-table__position" data-testid="product-table-position">
              {t('productTable.positionIndicator', {
                start: pageInfo.startLabel,
                end: pageInfo.endLabel,
                total: filteredRows.length,
              })}
            </span>
            <div className="product-table__page-nav">
              <button
                type="button"
                className="btn btn--secondary"
                onClick={goToPrevious}
                disabled={pageInfo.clampedPage <= 1}
                data-testid="product-table-prev-btn"
              >
                {t('productTable.previous')}
              </button>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={goToNext}
                disabled={pageInfo.clampedPage >= pageInfo.totalPages}
                data-testid="product-table-next-btn"
              >
                {t('productTable.next')}
              </button>
            </div>
          </div>
        </>
      )}

      {viewerProduct && (
        <ImageViewer product={viewerProduct} onClose={handleCloseViewer} />
      )}
    </div>
  );
}
