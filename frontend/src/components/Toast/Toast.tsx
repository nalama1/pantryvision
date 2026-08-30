import { useEffect } from 'react';
import './Toast.css';
import { useLanguage } from '../../i18n/LanguageContext';

/** Visual style of the banner: informational blue or red. */
export type ToastVariant = 'info' | 'error';

export interface ToastProps {
  /** Primary message shown in bold as the first line. */
  message: string;
  /** Optional secondary line (smaller, not bold). */
  description?: string;
  /** Color variant: 'info' (blue) or 'error' (red). Defaults to 'info'. */
  variant?: ToastVariant;
  onDismiss: () => void;
  durationMs?: number;
}

/**
 * Toast is a prominent, auto-dismissing banner shown in the inventory filters row.
 *
 * Accessibility: 'info' uses role="status" + aria-live="polite" (non-intrusive);
 * 'error' uses role="alert" + aria-live="assertive" so it is announced promptly.
 * Neither steals focus. The leading icon is decorative (aria-hidden) since the
 * variant/role already conveys the semantic meaning.
 */
export function Toast({
  message,
  description,
  variant = 'info',
  onDismiss,
  durationMs = 3000,
}: ToastProps) {
  const { t } = useLanguage();

  // Auto-dismiss after durationMs. The cleanup clears the timer if the toast
  // unmounts early (e.g. a new toast replaces it) to avoid a stale callback.
  useEffect(() => {
    const timer = setTimeout(onDismiss, durationMs);
    return () => clearTimeout(timer);
  }, [onDismiss, durationMs]);

  const isError = variant === 'error';
  // Icon reflects the action: info (ℹ) for edit, trash can (🗑) for delete — the
  // trash can matches the app's destructive-action button icon. Unicode entities
  // are used to avoid source-encoding issues with the emoji glyphs.
  const icon = isError ? '\u{1F5D1}\u{FE0F}' : '\u2139\u{FE0F}';

  return (
    <div
      className={`toast toast--${variant}`}
      role={isError ? 'alert' : 'status'}
      aria-live={isError ? 'assertive' : 'polite'}
      data-testid="success-toast"
    >
      <span className="toast__icon" aria-hidden="true">{icon}</span>
      <div className="toast__content">
        <span className="toast__message">{message}</span>
        {description && <span className="toast__description">{description}</span>}
      </div>
      <button
        type="button"
        className="toast__dismiss"
        onClick={onDismiss}
        aria-label={t('toast.dismiss')}
        data-testid="toast-dismiss"
      >
        &times;
      </button>
    </div>
  );
}