import { useState, useEffect, useCallback } from 'react';
import './InventoryDashboard.css';
import { listProducts } from '../../services/inventoryService';
import type { InventoryProduct } from '../../services/inventoryService';
import { getExpirationStatus } from './expirationStatus';

export function InventoryDashboard() {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    <div className="inventory-dashboard__grid" data-testid="inventory-grid">
      {products.map((product) => (
        <ProductCard key={product.productId} product={product} />
      ))}
    </div>
  );
}

function ProductCard({ product }: { product: InventoryProduct }) {
  const status = getExpirationStatus(product.expirationDate);
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
          <span className="inventory-card__badge inventory-card__badge--expired">Expired</span>
        )}
        {status === 'expiring-soon' && (
          <span className="inventory-card__badge inventory-card__badge--expiring-soon">Expiring Soon</span>
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
