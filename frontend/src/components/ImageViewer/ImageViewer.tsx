import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react';
import './ImageViewer.css';
import type { InventoryProduct } from '../../services/inventoryService';
import { useLanguage } from '../../i18n/LanguageContext';

export interface ImageViewerProps {
  product: InventoryProduct;
  onClose: () => void;
}

type ImageLoadStatus = 'loading' | 'loaded' | 'error';

/**
 * ImageViewer is an accessible modal lightbox that shows a single product image
 * at a larger size without leaving the table view (Req 7.3, 7.7).
 *
 * It displays the presigned imageUrl that list-products already returned, so it
 * makes no extra network/presign call. The presigned URL is short-lived (~300s):
 * if it has expired, the <img> onError path shows a graceful fallback rather than
 * a broken-image icon (Req 7.6).
 *
 * Focus restore to the triggering "View" button is handled by the parent
 * ProductTable (it holds the button refs), so this component only traps focus
 * within itself while open (Req 7.7).
 */
export function ImageViewer({ product, onClose }: ImageViewerProps) {
  const { t } = useLanguage();
  const [status, setStatus] = useState<ImageLoadStatus>('loading');

  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const displayName = product.productName || t('productTable.unnamedProduct');

  // On mount, move focus into the dialog (the close button is the safe default).
  useEffect(() => {
    closeButtonRef.current?.focus();
  }, []);

  // Focus trap: keep keyboard focus within the dialog while open, and close on
  // Escape (Req 7.7). We cycle across all currently focusable controls.
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== 'Tab') return;

      const focusable = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>('button:not([disabled])') ?? [],
      );
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  // Clicking the backdrop (outside the dialog card) closes the viewer.
  const handleOverlayClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (event.target === event.currentTarget) {
        onClose();
      }
    },
    [onClose],
  );

  return (
    <div
      className="image-viewer__overlay"
      onClick={handleOverlayClick}
      onKeyDown={handleKeyDown}
    >
      <div
        ref={dialogRef}
        className="image-viewer"
        role="dialog"
        aria-modal="true"
        aria-label={t('productTable.viewImageOf', { name: displayName })}
        data-testid="image-viewer-dialog"
      >
        <button
          ref={closeButtonRef}
          className="image-viewer__close"
          type="button"
          onClick={onClose}
          aria-label={t('productTable.closeViewer')}
          data-testid="image-viewer-close-btn"
        >
          ✕
        </button>

        <div className="image-viewer__body">
          {status === 'loading' && (
            <div className="image-viewer__status" data-testid="image-viewer-loading">
              <div className="spinner" role="status" aria-label={t('productTable.imageLoading')}></div>
              <p>{t('productTable.imageLoading')}</p>
            </div>
          )}

          {status === 'error' && (
            <div className="image-viewer__status" role="alert" data-testid="image-viewer-error">
              <div className="image-viewer__error-icon">🖼️</div>
              <p>{t('productTable.imageError')}</p>
            </div>
          )}

          {/* The <img> stays mounted (even while "loading") so its onLoad/onError
              fire; it is visually hidden until loaded to avoid a flash of a
              partial image. It is not rendered at all when there is no URL, but
              the parent never opens the viewer without one (Req 7.5). */}
          {product.imageUrl && status !== 'error' && (
            <img
              className={`image-viewer__image ${status === 'loaded' ? 'image-viewer__image--visible' : ''}`}
              src={product.imageUrl}
              alt={displayName}
              onLoad={() => setStatus('loaded')}
              onError={() => setStatus('error')}
              data-testid="image-viewer-img"
            />
          )}
        </div>
      </div>
    </div>
  );
}
