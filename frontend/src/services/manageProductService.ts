/**
 * Manage-product service for updating and soft-deleting inventory products.
 * Calls the update-product and delete-product API endpoints (Option A: a dedicated
 * pantryvision-manage-api RestApi, so both URLs derive from one base env var).
 *
 * All requests are signed with AWS Signature V4 via Cognito Identity Pool temporary
 * credentials (see signedFetch.ts), consistent with the other PantryVision endpoints.
 */
import { signedFetch } from './signedFetch';
// Reuse the canonical product shape returned by the backend; update-product returns
// the full updated record, so the service surfaces the same type the inventory uses.
import type { InventoryProduct } from './inventoryService';

export interface UpdateProductFields {
  productName: string;
  brand: string;
  presentation: string;
  expirationDate: string;
}

export type ManageProductErrorCode =
  | 'MISSING_PARAMS'
  | 'INVALID_PARAMS'
  | 'INVALID_DATE'
  | 'INVALID_JSON'
  | 'NOT_FOUND'
  | 'INTERNAL_ERROR'
  // TIMEOUT is a client-only code: it lets the UI distinguish an aborted request
  // (30s update / 10s delete) from a genuine backend error, even though both are
  // surfaced through the same ManageProductError type.
  | 'TIMEOUT'
  | 'UNKNOWN';

export class ManageProductError extends Error {
  code: ManageProductErrorCode;

  constructor(code: ManageProductErrorCode, message: string) {
    super(message);
    this.name = 'ManageProductError';
    this.code = code;
  }
}

const apiEndpoint = import.meta.env.VITE_MANAGE_API_ENDPOINT;

/**
 * Performs a signed fetch bounded by a client-side timeout.
 *
 * The backend Lambdas have their own timeouts, but the UI requirements mandate a
 * hard client-side ceiling (Req 4.4: 30s update, Req 5.6: 10s delete) so the user
 * is never left waiting on a stalled connection. We abort via AbortController and
 * translate the resulting AbortError into a ManageProductError('TIMEOUT'), so the
 * UI can treat a timeout identically to a failed response.
 */
async function signedFetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await signedFetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ManageProductError('TIMEOUT', 'Request timed out');
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Updates the editable fields of an existing product via the update-product Lambda.
 * On success the backend returns the complete updated record (with the preserved
 * imageKey, createdAt, quantity, unit), which we surface as InventoryProduct.
 */
export async function updateProduct(
  productId: string,
  fields: UpdateProductFields,
): Promise<InventoryProduct> {
  if (!apiEndpoint) {
    throw new Error('API endpoint not configured. Set VITE_MANAGE_API_ENDPOINT environment variable.');
  }

  const response = await signedFetchWithTimeout(
    `${apiEndpoint}/update-product`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ productId, ...fields }),
    },
    30000,
  );

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ManageProductError(
      errorBody.error || 'UNKNOWN',
      errorBody.message || `Update failed (HTTP ${response.status})`,
    );
  }

  return response.json() as Promise<InventoryProduct>;
}

/**
 * Soft-deletes a product via the delete-product Lambda. The backend marks the
 * record as deleted (it is not physically removed) and returns its productId.
 */
export async function deleteProduct(productId: string): Promise<{ productId: string }> {
  if (!apiEndpoint) {
    throw new Error('API endpoint not configured. Set VITE_MANAGE_API_ENDPOINT environment variable.');
  }

  const response = await signedFetchWithTimeout(
    `${apiEndpoint}/delete-product`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ productId }),
    },
    10000,
  );

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ManageProductError(
      errorBody.error || 'UNKNOWN',
      errorBody.message || `Delete failed (HTTP ${response.status})`,
    );
  }

  return response.json() as Promise<{ productId: string }>;
}
