/**
 * Classifies a product's expiration urgency relative to a reference date.
 * Used to visually highlight products that are expired or expiring soon.
 */

export type ExpirationStatus = 'expired' | 'expiring-soon' | 'normal';

const EXPIRING_SOON_THRESHOLD_DAYS = 7;
const MS_PER_DAY = 24 * 60 * 60 * 1000;

/**
 * Classifies a product's expiration status relative to the current date.
 *
 * - 'expired': expirationDate is before today
 * - 'expiring-soon': expirationDate is today through 7 days from today (inclusive)
 * - 'normal': expirationDate is more than 7 days away, or empty
 *
 * @param expirationDate - ISO 8601 date string (YYYY-MM-DD) or empty string
 * @param today - Reference date to compare against (defaults to current date)
 */
export function getExpirationStatus(expirationDate: string, today: Date = new Date()): ExpirationStatus {
  if (!expirationDate) {
    return 'normal';
  }

  // Normalize both dates to midnight UTC to compare by calendar day only
  const expiration = new Date(expirationDate + 'T00:00:00Z');
  const todayMidnight = new Date(
    Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate())
  );

  if (isNaN(expiration.getTime())) {
    return 'normal';
  }

  const diffDays = Math.round((expiration.getTime() - todayMidnight.getTime()) / MS_PER_DAY);

  if (diffDays < 0) {
    return 'expired';
  }

  if (diffDays <= EXPIRING_SOON_THRESHOLD_DAYS) {
    return 'expiring-soon';
  }

  return 'normal';
}
