import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react';
import './DeleteConfirmation.css';
import type { InventoryProduct } from '../../services/inventoryService';
import { deleteProduct, ManageProductError } from '../../services/manageProductService';
import { useLanguage } from '../../i18n/LanguageContext';

export interface DeleteConfirmationProps {
  product: InventoryProduct;
  onConfirmed: (productId: string) => void;
  onCancel: () => void;
}

/**
 * DeleteConfirmation is an accessible modal dialog that guards product deletion
 * behind an explicit confirmation step (Req 5.2-5.8).
 *
 * Accessibility: exposed to assistive tech as a modal via role="dialog" +
 * aria-modal="true"; the title labels the dialog (aria-labelledby) and the
 * message (which names the product) describes it (aria-describedby).
 */
export function DeleteConfirmation({ product, onConfirmed, onCancel }: DeleteConfirmationProps) {
  const { t } = useLanguage();
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  // Remember whatever element opened the dialog (the Delete control) so focus can
  // be handed back to it on close/cancel/success — a screen-reader user must not be
  // stranded at the top of the document after the dialog disappears (Req 5.5).
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // On mount: capture the opener and move focus into the dialog (Req 5.2).
  // Focusing the Cancel button is the safe default — it is the non-destructive action.
  useEffect(() => {
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    cancelButtonRef.current?.focus();
  }, []);

  // Restores focus to the opener, then invokes the given close callback. Centralized
  // so every exit path (cancel, Escape, success) returns focus consistently (Req 5.5).
  const closeWith = useCallback((callback: () => void) => {
    previouslyFocusedRef.current?.focus();
    callback();
  }, []);

  const handleCancel = useCallback(() => {
    // Cancel is a no-op on the network and is disabled while a delete is in flight.
    if (isDeleting) return;
    closeWith(onCancel);
  }, [isDeleting, closeWith, onCancel]);

  const handleConfirm = useCallback(async () => {
    if (isDeleting) return;
    setIsDeleting(true);
    setErrorMessage(null);

    try {
      await deleteProduct(product.productId);
      // Success: hand focus back before unmounting, then let the parent remove the card.
      closeWith(() => onConfirmed(product.productId));
    } catch (err) {
      // A client-side timeout surfaces as ManageProductError('TIMEOUT') and is treated
      // identically to any backend failure: keep the card, re-enable controls (Req 5.8).
      const message =
        err instanceof ManageProductError ? err.message : t('deleteConfirmation.error');
      setErrorMessage(message || t('deleteConfirmation.error'));
      setIsDeleting(false);
    }
  }, [isDeleting, product.productId, closeWith, onConfirmed, t]);

  // Focus trap: while the dialog is open, keyboard focus must stay within it so a
  // keyboard/screen-reader user cannot tab into the (inert) content behind the modal
  // (Req 5.3). We only ever expose two controls, so we cycle between them explicitly:
  // Tab past the last wraps to the first, Shift+Tab before the first wraps to the last.
  // Escape cancels the dialog (Req 5.5).
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        handleCancel();
        return;
      }

      if (event.key !== 'Tab') return;

      const focusable = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled])',
        ) ?? [],
      );
      if (focusable.length === 0) {
        // All controls disabled (delete in progress): keep focus inside the dialog.
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
    [handleCancel],
  );

  return (
    <div className="delete-confirmation__overlay">
      <div
        ref={dialogRef}
        className="delete-confirmation"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-confirmation-title"
        aria-describedby="delete-confirmation-message"
        data-testid="delete-confirm-dialog"
        onKeyDown={handleKeyDown}
      >
        <h2 id="delete-confirmation-title" className="delete-confirmation__title">
          {t('deleteConfirmation.title')}
        </h2>

        <p id="delete-confirmation-message" className="delete-confirmation__message">
          {t('deleteConfirmation.message', { name: product.productName })}
        </p>

        {errorMessage && (
          <div
            className="delete-confirmation__error"
            data-testid="delete-error"
            role="alert"
          >
            {errorMessage}
          </div>
        )}

        <div className="delete-confirmation__actions">
          <button
            ref={cancelButtonRef}
            className="btn btn--secondary"
            type="button"
            onClick={handleCancel}
            disabled={isDeleting}
            data-testid="delete-cancel-btn"
          >
            {t('deleteConfirmation.cancel')}
          </button>
          <button
            className="btn btn--danger"
            type="button"
            onClick={handleConfirm}
            disabled={isDeleting}
            data-testid="delete-confirm-btn"
          >
            {isDeleting ? t('deleteConfirmation.deleting') : t('deleteConfirmation.confirm')}
          </button>
        </div>
      </div>
    </div>
  );
}
