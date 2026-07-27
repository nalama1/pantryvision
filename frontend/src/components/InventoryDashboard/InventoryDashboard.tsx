import { useState, useEffect, useCallback, useMemo } from 'react';
import './InventoryDashboard.css';
import { listProducts } from '../../services/inventoryService';
import type { InventoryProduct } from '../../services/inventoryService';
import { getExpirationStatus, type ExpirationStatus } from './expirationStatus';

export function InventoryDashboard() {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<ExpirationStatus | null>(null);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listProducts();
      setProducts(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load inventory';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  // Compute status for each product once, reused for both counts and filtering
  const productsWithStatus = useMemo(
    () => products.map((product) => ({
      product,
      status: getExpirationStatus(product.expirationDate),
    })),
    [products],
  );

  const counts = useMemo(() => {
    const result: Record<ExpirationStatus, number> = { expired: 0, 'expiring-soon': 0, normal: 0 };
    for (const { status } of productsWithStatus) {
      result[status] += 1;
    }
    return result;
  }, [productsWithStatus]);

  const filteredProducts = useMemo(() => {
    if (!activeFilter) return productsWithStatus;
    return productsWithStatus.filter(({ status }) => status === activeFilter);
  }, [productsWithStatus, activeFilter]);

  const handleToggleFilter = useCallback((status: ExpirationStatus) => {
    setActiveFilter((current) => (current === status ? null : status));
  }, []);

  if (loading) {
    return (
      <div className="inventory-dashboard__loading" data-testid="inventory-loading">
        <div className="spinner" role="status" aria-label="Loading inventory"></div>
        <p>Loading your inventory...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="inventory-dashboard__error" role="alert" data-testid="inventory-error">
        <p>{error}</p>
        <button className="btn btn--primary" onClick={fetchProducts} data-testid="retry-btn">
          Retry
        </button>
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="inventory-dashboard__empty" data-testid="inventory-empty">
        <div className="inventory-dashboard__empty-icon">📦</div>
        <p>No products saved yet. Upload a photo to get started!</p>
      </div>
    );
  }

  return (
    <div data-testid="inventory-dashboard">
      <div className="inventory-filters" data-testid="inventory-filters">
        <button
          type="button"
          className={`inventory-filter inventory-filter--expired ${activeFilter === 'expired' ? 'inventory-filter--active' : ''}`}
          onClick={() => handleToggleFilter('expired')}
          data-testid="filter-expired"
          aria-pressed={activeFilter === 'expired'}
        >
          ❌ Expired ({counts.expired})
        </button>
        <button
          type="button"
          className={`inventory-filter inventory-filter--expiring-soon ${activeFilter === 'expiring-soon' ? 'inventory-filter--active' : ''}`}
          onClick={() => handleToggleFilter('expiring-soon')}
          data-testid="filter-expiring-soon"
          aria-pressed={activeFilter === 'expiring-soon'}
        >
          ⏰ Expiring Soon ({counts['expiring-soon']})
        </button>
        <button
          type="button"
          className={`inventory-filter inventory-filter--normal ${activeFilter === 'normal' ? 'inventory-filter--active' : ''}`}
          onClick={() => handleToggleFilter('normal')}
          data-testid="filter-ok"
          aria-pressed={activeFilter === 'normal'}
        >
          ✅ Good ({counts.normal})
        </button>
      </div>

      {filteredProducts.length === 0 ? (
        <div className="inventory-dashboard__empty" data-testid="inventory-filtered-empty">
          <p>No products match this filter.</p>
        </div>
      ) : (
        <div className="inventory-dashboard__grid" data-testid="inventory-grid">
          {filteredProducts.map(({ product, status }) => (
            <ProductCard key={product.productId} product={product} status={status} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProductCard({ product, status }: { product: InventoryProduct; status: ExpirationStatus }) {
  const cardClass = `inventory-card inventory-card--${status}`;

  return (
    <div className={cardClass} data-testid="product-card">
      <div className="inventory-card__image-wrapper">
        {product.imageUrl ? (
          <img
            className="inventory-card__image"
            src={product.imageUrl}
            alt={product.productName || 'Product photo'}
          />
        ) : (
          <div className="inventory-card__placeholder" aria-label="No image available">
            📷
          </div>
        )}
        {status === 'expired' && (
          <span className="inventory-card__badge inventory-card__badge--expired">❌ Expired</span>
        )}
        {status === 'expiring-soon' && (
          <span className="inventory-card__badge inventory-card__badge--expiring-soon">⏰ Expiring Soon</span>
        )}
        {status === 'normal' && (
          <span className="inventory-card__badge inventory-card__badge--normal">✅ Fresh</span>
        )}
      </div>
      <div className="inventory-card__content">
        <h3 className="inventory-card__name">{product.productName || 'Unnamed product'}</h3>
        {product.brand && <p className="inventory-card__brand">{product.brand}</p>}
        {product.presentation && <p className="inventory-card__presentation">{product.presentation}</p>}
        {product.expirationDate && (
          <p className="inventory-card__expiration">Expires: {product.expirationDate}</p>
        )}
        <p className="inventory-card__quantity">
          {product.quantity} {product.unit}
        </p>
      </div>
    </div>
  );
}
