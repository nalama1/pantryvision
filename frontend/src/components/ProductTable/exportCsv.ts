/**
 * Pure CSV building + browser download helpers for the ProductTable export.
 *
 * Kept separate from the component so the escaping/quoting logic is easy to
 * unit-test in isolation. The image column is intentionally excluded (it is an
 * on-demand action, not tabular data).
 */
import type { InventoryProduct } from '../../services/inventoryService';
import type { ExpirationStatus } from '../InventoryDashboard/expirationStatus';

export interface ExportRow {
  product: InventoryProduct;
  status: ExpirationStatus;
}

/** Localized header + status/active labels, injected so the CSV matches the UI language. */
export interface ExportLabels {
  number: string;
  expires: string;
  name: string;
  brand: string;
  presentation: string;
  quantity: string;
  status: string;
  active: string;
  statusExpired: string;
  statusExpiringSoon: string;
  statusGood: string;
  activeLabel: string;
  inactiveLabel: string;
  unnamedProduct: string;
}

const STATUS_TO_LABEL_KEY: Record<ExpirationStatus, keyof Pick<ExportLabels, 'statusExpired' | 'statusExpiringSoon' | 'statusGood'>> = {
  expired: 'statusExpired',
  'expiring-soon': 'statusExpiringSoon',
  normal: 'statusGood',
};

/**
 * Escapes a single CSV field per RFC 4180: wrap in double quotes when the value
 * contains a comma, quote, or newline, and double any embedded quotes.
 */
function escapeCsvField(value: string | number): string {
  const str = String(value ?? '');
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Builds the CSV text (with header row) for the given rows, in display order.
 * Uses CRLF line endings for maximum spreadsheet compatibility.
 */
export function buildCsv(rows: ExportRow[], labels: ExportLabels): string {
  const header = [
    labels.number,
    labels.status,
    labels.expires,
    labels.name,
    labels.brand,
    labels.presentation,
    labels.quantity,
    labels.active,
  ];

  const lines = [header.map(escapeCsvField).join(',')];

  rows.forEach(({ product, status }, index) => {
    const statusLabel = labels[STATUS_TO_LABEL_KEY[status]];
    const activeLabel = product.deleted === true ? labels.inactiveLabel : labels.activeLabel;
    const line = [
      index + 1,
      statusLabel,
      product.expirationDate || '',
      product.productName || labels.unnamedProduct,
      product.brand || '',
      product.presentation || '',
      `${product.quantity} ${product.unit}`.trim(),
      activeLabel,
    ];
    lines.push(line.map(escapeCsvField).join(','));
  });

  return lines.join('\r\n');
}

/**
 * Triggers a client-side download of the CSV. A UTF-8 BOM is prepended so Excel
 * renders accented characters (á, é, ñ, ...) correctly instead of mojibake.
 */
export function downloadCsv(csv: string, filename: string): void {
  const bom = '\uFEFF';
  const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/** Builds a dated filename like "pantryvision-inventory-2026-08-30.csv". */
export function buildExportFilename(today: Date = new Date()): string {
  const iso = today.toISOString().slice(0, 10);
  return `pantryvision-inventory-${iso}.csv`;
}
