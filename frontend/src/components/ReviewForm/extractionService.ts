import type { ExtractionResult } from './types';
import { signedFetch } from '../../services/signedFetch';

/** Error codes returned by the extraction API */
export type ExtractionErrorCode =
  | 'IMAGE_NOT_FOUND'
  | 'MISSING_PARAMS'
  | 'INVALID_OBJECT_KEY'
  | 'INTERNAL_ERROR'
  | 'UNKNOWN';

/** Typed error for extraction failures, carries a code for programmatic handling */
export class ExtractionServiceError extends Error {
  code: ExtractionErrorCode;

  constructor(code: ExtractionErrorCode, message: string) {
    super(message);
    this.name = 'ExtractionServiceError';
    this.code = code;
  }
}

/**
 * Requests AI data extraction for a previously uploaded product image.
 * The backend Lambda retrieves the image from S3 and invokes Bedrock
 * to extract structured product data.
 *
 * Signed with AWS Signature V4 via Cognito Identity Pool temporary credentials (see signedFetch.ts)
 */
export async function requestExtraction(objectKey: string): Promise<ExtractionResult> {
  const apiEndpoint = import.meta.env.VITE_EXTRACT_API_ENDPOINT;

  if (!apiEndpoint) {
    throw new Error('API endpoint not configured. Set VITE_EXTRACT_API_ENDPOINT environment variable.');
  }

  const response = await signedFetch(`${apiEndpoint}/extract-product-data`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ objectKey }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ExtractionServiceError(
      errorBody.error || 'UNKNOWN',
      errorBody.message || `Extraction failed (HTTP ${response.status})`,
    );
  }

  return response.json() as Promise<ExtractionResult>;
}
