/**
 * Upload service for the PhotoUploader component.
 * Handles presigned URL requests and direct S3 uploads with progress tracking.
 */

export interface PresignedUrlResponse {
  uploadUrl: string;
  objectKey: string;
}

/** Error codes that identify specific upload failure modes */
export type UploadErrorCode = 'NETWORK_ERROR' | 'TIMEOUT' | 'PRESIGN_EXPIRED';

/** Typed error for upload failures, carries a code for programmatic retry decisions */
export class UploadServiceError extends Error {
  code: UploadErrorCode;

  constructor(code: UploadErrorCode, message: string) {
    super(message);
    this.name = 'UploadServiceError';
    this.code = code;
  }
}

/**
 * Requests a presigned PUT URL from the backend API.
 * The backend generates a unique S3 object key and returns a time-limited URL
 * that allows direct upload without exposing AWS credentials.
 *
 * NOTE (IAM Auth / AWS Signature V4):
 * The API Gateway endpoint uses AWS_IAM authorization. In production, the fetch
 * call below must be signed with AWS Signature V4. When using AWS Amplify, this
 * is handled automatically via `Amplify.API.post(...)` which signs requests using
 * the authenticated user's credentials from `@aws-amplify/auth`.
 *
 * TODO: Replace raw fetch with Amplify API call once Amplify Auth is configured:
 *   import { post } from 'aws-amplify/api';
 *   const response = await post({ apiName: 'uploadApi', path: '/upload-url', options: { body } });
 */
export async function requestPresignedUrl(
  contentType: string,
  fileExtension: string,
): Promise<PresignedUrlResponse> {
  const apiEndpoint = import.meta.env.VITE_API_ENDPOINT;

  if (!apiEndpoint) {
    throw new Error('API endpoint not configured. Set VITE_API_ENDPOINT environment variable.');
  }

  const response = await fetch(`${apiEndpoint}/upload-url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contentType, fileExtension }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(
      errorBody.message || `Failed to get upload URL (HTTP ${response.status})`,
    );
  }

  const data: PresignedUrlResponse = await response.json();
  return data;
}

/**
 * Uploads a file directly to S3 using a presigned PUT URL.
 * Uses XMLHttpRequest instead of fetch to support upload progress tracking.
 *
 * Throws UploadServiceError with specific codes:
 * - PRESIGN_EXPIRED: S3 returned 403, indicating the presigned URL has expired
 * - TIMEOUT: Upload did not complete within the timeout period
 * - NETWORK_ERROR: A network-level failure occurred (no response from server)
 *
 * @param file - The file to upload
 * @param presignedUrl - The presigned PUT URL from the backend
 * @param onProgress - Callback invoked with progress percentage (0-100)
 * @param timeoutMs - Upload timeout in milliseconds (default: 30000)
 */
export function uploadToS3(
  file: File,
  presignedUrl: string,
  onProgress?: (percent: number) => void,
  timeoutMs: number = 30_000,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(percent);
      }
    };

    xhr.onload = () => {
      if (xhr.status === 200) {
        resolve();
      } else if (xhr.status === 403) {
        // 403 from S3 means the presigned URL has expired
        reject(new UploadServiceError('PRESIGN_EXPIRED', 'Upload URL has expired. Requesting a new one.'));
      } else {
        reject(new UploadServiceError('NETWORK_ERROR', `S3 upload failed with status ${xhr.status}`));
      }
    };

    xhr.onerror = () => {
      reject(new UploadServiceError('NETWORK_ERROR', 'Network error during upload. Please check your connection.'));
    };

    xhr.ontimeout = () => {
      reject(new UploadServiceError('TIMEOUT', 'Upload timed out. The file may be too large for your connection speed.'));
    };

    xhr.timeout = timeoutMs;
    xhr.open('PUT', presignedUrl);
    xhr.setRequestHeader('Content-Type', file.type);
    xhr.send(file);
  });
}
