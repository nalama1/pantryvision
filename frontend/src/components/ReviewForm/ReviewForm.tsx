import { useState, useCallback, type FormEvent } from 'react';
import './ReviewForm.css';
import type { ReviewFormProps, ProductData, ConfidenceLevel } from './types';

/**
 * ReviewForm displays extracted product data for user review and editing.
 * Fields with low confidence are visually highlighted to prompt verification.
 * productName is required; all other fields are optional.
 */
export function ReviewForm({ extractionResult, onConfirm, onCancel }: ReviewFormProps) {
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
        setProductNameError('Product name is required.');
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
          AI extraction was unavailable. Please fill in the details manually.
        </div>
      )}

      {/* Product Name */}
      <div className="review-form__field">
        <label htmlFor="review-productName">Product Name *</label>
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
        <label htmlFor="review-brand">Brand</label>
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
        />
      </div>

      {/* Presentation */}
      <div className="review-form__field">
        <label htmlFor="review-presentation">Presentation</label>
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
        />
      </div>

      {/* Expiration Date */}
      <div className="review-form__field">
        <label htmlFor="review-expirationDate">Expiration Date</label>
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
          Cancel
        </button>
        <button
          className="btn btn--primary"
          type="submit"
          data-testid="submit-btn"
        >
          Confirm
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
function ConfidenceIndicator({ level, testId }: { level: ConfidenceLevel; testId: string }) {
  if (level === 'low') {
    return (
      <span
        className="review-form__confidence review-form__confidence--low"
        data-testid={testId}
        aria-label="Low confidence"
      >
        ⚠️ Low confidence
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
        Medium confidence
      </span>
    );
  }

  return (
    <span
      className="review-form__confidence review-form__confidence--high"
      data-testid={testId}
      aria-label="High confidence"
    >
      High confidence
    </span>
  );
}
