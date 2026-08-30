import { useState, useCallback, useEffect, useRef, type FormEvent } from 'react';
import './EditForm.css';
import { useLanguage } from '../../i18n/LanguageContext';
import {
  updateProduct,
  ManageProductError,
} from '../../services/manageProductService';
import type { InventoryProduct } from '../../services/inventoryService';

// Mirrors the backend limit (productName 1-200 chars after trim, Req 4.8). Kept as a
// constant so the validation rule reads clearly and stays in one place.
const PRODUCT_NAME_MAX_LENGTH = 200;

export interface EditFormProps {
  product: InventoryProduct;
  onSuccess: (updated: InventoryProduct) => void;
  onCancel: () => void;
}

/**
 * EditForm is a modal that lets the user edit a product's editable fields
 * (productName, brand, presentation, expirationDate), pre-filled from the selected
 * product (Req 4.2). It reuses the ReviewForm field layout/validation conventions
 * (controlled inputs, inline error via role="alert", btn classes) and calls the
 * update-product endpoint through manageProductService.
 *
 * The AI-extraction fallback principle applies here too: this is a plain manual
 * form, so the user can always correct/complete the data by hand.
 */
export function EditForm({ product, onSuccess, onCancel }: EditFormProps) {
  const { t } = useLanguage();

  // Controlled inputs pre-filled from the current product values (Req 4.2).
  const [productName, setProductName] = useState(product.productName ?? '');
  const [brand, setBrand] = useState(product.brand ?? '');
  const [presentation, setPresentation] = useState(product.presentation ?? '');
  const [expirationDate, setExpirationDate] = useState(product.expirationDate ?? '');

  const [productNameError, setProductNameError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Focus the first field on open so keyboard users land inside the dialog (a11y).
  const firstFieldRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    firstFieldRef.current?.focus();
  }, []);

  // Escape-to-cancel is a common modal affordance; it must not fire mid-request so
  // the user cannot dismiss the dialog while an update is in flight.
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSubmitting) {
        onCancel();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onCancel, isSubmitting]);

  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();

      const trimmedName = productName.trim();

      // Client-side validation before submit (Req 4.7, 4.8): block submit, retain
      // the entered values, and surface an inline validation message.
      if (!trimmedName) {
        setProductNameError(t('editForm.productNameRequired'));
        return;
      }
      if (trimmedName.length > PRODUCT_NAME_MAX_LENGTH) {
        setProductNameError(t('editForm.productNameTooLong'));
        return;
      }

      setProductNameError(null);
      setSubmitError(null);
      setIsSubmitting(true);

      try {
        const updated = await updateProduct(product.productId, {
          productName: trimmedName,
          brand: brand.trim(),
          presentation: presentation.trim(),
          expirationDate: expirationDate.trim(),
        });
        // Success: hand the resolved record back so the caller can close the modal
        // and update the card in place (Req 4.5).
        onSuccess(updated);
      } catch (err) {
        // On error (including TIMEOUT) keep the modal open with the entered values,
        // re-enable submit, and show an error message (Req 4.6).
        if (err instanceof ManageProductError) {
          // NOT_FOUND gets a friendlier "no longer exists" message; other codes fall
          // back to the backend-provided message.
          setSubmitError(
            err.code === 'NOT_FOUND'
              ? t('editForm.notFoundError')
              : err.message || t('editForm.updateError'),
          );
        } else {
          setSubmitError(t('editForm.updateError'));
        }
        setIsSubmitting(false);
      }
    },
    [productName, brand, presentation, expirationDate, product.productId, onSuccess, t],
  );

  return (
    <div
      className="edit-form__overlay"
      data-testid="edit-form-overlay"
      // Clicking the backdrop cancels, but only when idle so an in-flight request
      // cannot be interrupted by an accidental click-through.
      onClick={() => {
        if (!isSubmitting) onCancel();
      }}
    >
      <div
        className="edit-form__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-form-title"
        // Stop backdrop-click cancellation when interacting inside the dialog.
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="edit-form-title" className="edit-form__title">
          {t('editForm.title')}
        </h2>

        <form
          className="edit-form"
          data-testid="edit-form"
          onSubmit={handleSubmit}
          noValidate
          aria-label={t('editForm.title')}
        >
          {/* Submit error banner (Req 4.6) */}
          {submitError && (
            <div className="edit-form__submit-error" data-testid="edit-error" role="alert">
              {submitError}
            </div>
          )}

          {/* Product Name (required) */}
          <div className="edit-form__field">
            <label htmlFor="edit-productName">{t('editForm.productNameLabel')}</label>
            <input
              ref={firstFieldRef}
              id="edit-productName"
              type="text"
              value={productName}
              onChange={(e) => {
                setProductName(e.target.value);
                if (productNameError) setProductNameError(null);
              }}
              data-testid="edit-field-productName"
              aria-required="true"
              aria-invalid={!!productNameError}
              aria-describedby={productNameError ? 'edit-error-productName' : undefined}
              disabled={isSubmitting}
              className="edit-form__input"
            />
            {productNameError && (
              <span
                id="edit-error-productName"
                className="edit-form__error"
                data-testid="edit-error-productName"
                role="alert"
              >
                {productNameError}
              </span>
            )}
          </div>

          {/* Brand (optional) */}
          <div className="edit-form__field">
            <label htmlFor="edit-brand">{t('editForm.brandLabel')}</label>
            <input
              id="edit-brand"
              type="text"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              data-testid="edit-field-brand"
              disabled={isSubmitting}
              className="edit-form__input"
            />
          </div>

          {/* Presentation (optional) */}
          <div className="edit-form__field">
            <label htmlFor="edit-presentation">{t('editForm.presentationLabel')}</label>
            <input
              id="edit-presentation"
              type="text"
              value={presentation}
              onChange={(e) => setPresentation(e.target.value)}
              data-testid="edit-field-presentation"
              disabled={isSubmitting}
              className="edit-form__input"
            />
          </div>

          {/* Expiration Date (optional) */}
          <div className="edit-form__field">
            <label htmlFor="edit-expirationDate">{t('editForm.expirationDateLabel')}</label>
            <input
              id="edit-expirationDate"
              type="date"
              value={expirationDate}
              onChange={(e) => setExpirationDate(e.target.value)}
              data-testid="edit-field-expirationDate"
              disabled={isSubmitting}
              className="edit-form__input"
            />
          </div>

          {/* Actions */}
          <div className="edit-form__actions">
            <button
              className="btn btn--secondary"
              type="button"
              onClick={onCancel}
              disabled={isSubmitting}
              data-testid="edit-cancel-btn"
            >
              {t('editForm.cancel')}
            </button>
            <button
              className="btn btn--primary"
              type="submit"
              disabled={isSubmitting}
              data-testid="edit-submit-btn"
            >
              {isSubmitting ? t('editForm.saving') : t('editForm.save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
