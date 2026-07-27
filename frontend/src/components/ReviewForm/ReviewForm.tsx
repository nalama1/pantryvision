import { useState, useCallback, type FormEvent } from 'react';
import './ReviewForm.css';
import type { ReviewFormProps, ProductData, ConfidenceLevel } from './types';
import { useLanguage } from '../../i18n/LanguageContext';

/**
 * ReviewForm displays extracted product data for user review and editing.
 * Fields with low confidence are visually highlighted to prompt verification.
 * productName is required; all other fields are optional.
 */
export function ReviewForm({ extractionResult, onConfirm, onCancel }: ReviewFormProps) {
  const { t } = useLanguage();
  const [productName, setProductName] = useState(extractionResult.productName ?? '');
  const [brand, setBrand] = useState(extractionResult.brand ?? '');
  const [presentation, setPresentation] = useState(extractionResult.presentation ?? '');
  const [expirationDate, setExpirationDate] = useState(extractionResult.expirationDate ?? '');
  const [productNameError, setProductNameError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();

      // Validate productName is non-empty (trimmed)
      if (!productName.trim()) {
        setProductNameError(t('reviewForm.productNameRequired'));
        return;
      }

      setProductNameError(null);

      const data: ProductData = {
        productName: productName.trim(),
        brand: brand.trim(),
        presentation: presentation.trim(),
        expirationDate: expirationDate.trim(),
      };

      onConfirm(data);
    },
    [productName, brand, presentation, expirationDate, onConfirm],
  );

  const handleCancel = useCallback(() => {
    onCancel();
  }, [onCancel]);

  return (
    <form
      className="review-form"
      data-testid="review-form"
      onSubmit={handleSubmit}
      noValidate
      aria-label="Review extracted product data"
    >
      {/* AI extraction error message */}
      {extractionResult.error && (
        <div
          className="review-form__extraction-error"
          data-testid="extraction-error"
          role="alert"
        >
          {t('reviewForm.extractionError')}
        </div>
      )}

      {/* Product Name */}
      <div className="review-form__field">
        <label htmlFor="review-productName">{t('reviewForm.productNameLabel')}</label>
        <input
          id="review-productName"
          type="text"
          value={productName}
          onChange={(e) => {
            setProductName(e.target.value);
            if (productNameError) setProductNameError(null);
          }}
          data-testid="field-productName"
          aria-required="true"
          aria-invalid={!!productNameError}
          aria-describedby={productNameError ? 'error-productName' : undefined}
          className={getFieldClassName(extractionResult.confidence.productName)}
        />
        <ConfidenceIndicator
          level={extractionResult.confidence.productName}
          testId="confidence-productName"
          t={t}
        />
        {productNameError && (
          <span
            id="error-productName"
            className="review-form__error"
            data-testid="error-productName"
            role="alert"
          >
            {productNameError}
          </span>
        )}
      </div>

      {/* Brand */}
      <div className="review-form__field">
        <label htmlFor="review-brand">{t('reviewForm.brandLabel')}</label>
        <input
          id="review-brand"
          type="text"
          value={brand}
          onChange={(e) => setBrand(e.target.value)}
          data-testid="field-brand"
          className={getFieldClassName(extractionResult.confidence.brand)}
        />
        <ConfidenceIndicator
          level={extractionResult.confidence.brand}
          testId="confidence-brand"
          t={t}
        />
      </div>

      {/* Presentation */}
      <div className="review-form__field">
        <label htmlFor="review-presentation">{t('reviewForm.presentationLabel')}</label>
        <input
          id="review-presentation"
          type="text"
          value={presentation}
          onChange={(e) => setPresentation(e.target.value)}
          data-testid="field-presentation"
          className={getFieldClassName(extractionResult.confidence.presentation)}
        />
        <ConfidenceIndicator
          level={extractionResult.confidence.presentation}
          testId="confidence-presentation"
          t={t}
        />
      </div>

      {/* Expiration Date */}
      <div className="review-form__field">
        <label htmlFor="review-expirationDate">{t('reviewForm.expirationDateLabel')}</label>
        <input
          id="review-expirationDate"
          type="date"
          value={expirationDate}
          onChange={(e) => setExpirationDate(e.target.value)}
          data-testid="field-expirationDate"
          className={getFieldClassName(extractionResult.confidence.expirationDate)}
        />
        <ConfidenceIndicator
          level={extractionResult.confidence.expirationDate}
          testId="confidence-expirationDate"
          t={t}
        />
      </div>

      {/* Actions */}
      <div className="review-form__actions">
        <button
          className="btn btn--secondary"
          type="button"
          onClick={handleCancel}
          data-testid="cancel-btn"
        >
          {t('reviewForm.cancel')}
        </button>
        <button
          className="btn btn--primary"
          type="submit"
          data-testid="submit-btn"
        >
          {t('reviewForm.confirm')}
        </button>
      </div>
    </form>
  );
}

/** Returns CSS class names for an input based on its confidence level */
function getFieldClassName(confidence: ConfidenceLevel): string {
  if (confidence === 'low') {
    return 'review-form__input review-form__input--low-confidence';
  }
  return 'review-form__input';
}

/** Displays a confidence indicator next to a field */
function ConfidenceIndicator({
  level,
  testId,
  t,
}: {
  level: ConfidenceLevel;
  testId: string;
  t: (key: string, params?: Record<string, string | number>) => string;
}) {
  if (level === 'low') {
    return (
      <span
        className="review-form__confidence review-form__confidence--low"
        data-testid={testId}
        aria-label="Low confidence"
      >
        {t('reviewForm.lowConfidence')}
      </span>
    );
  }

  if (level === 'medium') {
    return (
      <span
        className="review-form__confidence review-form__confidence--medium"
        data-testid={testId}
        aria-label="Medium confidence"
      >
        {t('reviewForm.mediumConfidence')}
      </span>
    );
  }

  return (
    <span
      className="review-form__confidence review-form__confidence--high"
      data-testid={testId}
      aria-label="High confidence"
    >
      {t('reviewForm.highConfidence')}
    </span>
  );
}
