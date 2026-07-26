/**
 * Product service for saving confirmed products to the inventory.
 * Calls the save-product API endpoint to persist product data in DynamoDB.
 */

export interface SaveProductRequest {
  productName: string;
  brand: string;
  presentation: string;
  expirationDate: string;
  imageKey: string;
  quantity?: number;
  unit?: string;
}

export interface SaveProductResponse {
  productId: string;
  productName: string;
  brand: string;
  presentation: string;
  expirationDate: string;
  imageKey: string;
  createdAt: string;
  quantity: number;
  unit: string;
}

export type SaveProductErrorCode =
  | 'MISSING_PARAMS'
  | 'INVALID_IMAGE_KEY'
  | 'INVALID_QUANTITY'
  | 'INTERNAL_ERROR'
  | 'UNKNOWN';

export class SaveProductError extends Error {
  code: SaveProductErrorCode;

  constructor(code: SaveProductErrorCode, message: string) {
    super(message);
    this.name = 'SaveProductError';
    this.code = code;
  }
}

/**
 * Saves a confirmed product to the inventory via the save-product Lambda.
 *
 * NOTE (IAM Auth / AWS Signature V4):
 * The API Gateway endpoint uses AWS_IAM authorization in production.
 * Currently set to NONE for local testing.
 *
 * TODO: Replace raw fetch with Amplify API call once Amplify Auth is configured.
 */
export async function saveProduct(request: SaveProductRequest): Promise<SaveProductResponse> {
  const apiEndpoint = import.meta.env.VITE_SAVE_API_ENDPOINT;

  if (!apiEndpoint) {
    throw new Error('API endpoint not configured. Set VITE_SAVE_API_ENDPOINT environment variable.');
  }

  const response = await fetch(`${apiEndpoint}/save-product`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new SaveProductError(
      errorBody.error || 'UNKNOWN',
      errorBody.message || `Save failed (HTTP ${response.status})`,
    );
  }

  return response.json() as Promise<SaveProductResponse>;
}
