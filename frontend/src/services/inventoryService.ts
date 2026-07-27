/**
 * Inventory service for retrieving saved products.
 * Calls the list-products API endpoint to fetch the full inventory with presigned image URLs.
 */
import { signedFetch } from './signedFetch';

export interface InventoryProduct {
  productId: string;
  productName: string;
  brand: string;
  presentation: string;
  expirationDate: string;
  imageKey: string;
  imageUrl: string | null;
  createdAt: string;
  quantity: number;
  unit: string;
}

export type ListProductsErrorCode = 'INTERNAL_ERROR' | 'UNKNOWN';

export class ListProductsError extends Error {
  code: ListProductsErrorCode;

  constructor(code: ListProductsErrorCode, message: string) {
    super(message);
    this.name = 'ListProductsError';
    this.code = code;
  }
}

/**
 * Retrieves the full list of saved products from the inventory.
 *
 * Signed with AWS Signature V4 via Cognito Identity Pool temporary credentials (see signedFetch.ts)
 */
export async function listProducts(): Promise<InventoryProduct[]> {
  const apiEndpoint = import.meta.env.VITE_LIST_API_ENDPOINT;

  if (!apiEndpoint) {
    throw new Error('API endpoint not configured. Set VITE_LIST_API_ENDPOINT environment variable.');
  }

  const response = await signedFetch(`${apiEndpoint}/list-products`, {
    method: 'GET',
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ListProductsError(
      errorBody.error || 'UNKNOWN',
      errorBody.message || `Failed to load inventory (HTTP ${response.status})`,
    );
  }

  return response.json() as Promise<InventoryProduct[]>;
}
