/**
 * File validation utility for the PhotoUploader component.
 * Validates MIME type, file size, and image resolution before initiating upload.
 */

// Only the codes relevant to client-side file validation are used here;
// the full UploadError type includes network/server codes used elsewhere.
export interface UploadError {
  code:
    | 'INVALID_TYPE'
    | 'FILE_TOO_LARGE'
    | 'INVALID_RESOLUTION'
    | 'NETWORK_ERROR'
    | 'TIMEOUT'
    | 'PRESIGN_FAILED'
    | 'PREVIEW_FAILED';
  message: string;
}

export type ValidationResult = { valid: true } | { valid: false; error: UploadError };

const ALLOWED_MIME_TYPES: ReadonlySet<string> = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
]);

const MAX_FILE_SIZE_BYTES = 5_242_880; // 5 MB

const MIN_RESOLUTION = 200;
const MAX_RESOLUTION = 8000; // Raised from 4096 to accommodate modern phone camera resolutions (e.g., 4160x3120); backend resizes to 1024px before Bedrock, so no cost impact.

/**
 * Validates a file for upload eligibility.
 *
 * Checks are performed in order:
 * 1. MIME type must be jpeg, png, or webp
 * 2. File size must be <= 5 MB
 * 3. Image resolution must be between 200×200 and 4096×4096
 *
 * Resolution validation is async because it loads the image via an
 * object URL to read naturalWidth/naturalHeight.
 */
export async function validateFile(file: File): Promise<ValidationResult> {
  // 1. MIME type check
  if (!ALLOWED_MIME_TYPES.has(file.type)) {
    return {
      valid: false,
      error: {
        code: 'INVALID_TYPE',
        message: 'File type not supported. Please select a JPEG, PNG, or WebP image.',
      },
    };
  }

  // 2. File size check
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return {
      valid: false,
      error: {
        code: 'FILE_TOO_LARGE',
        message: 'File exceeds the maximum allowed size of 5 MB.',
      },
    };
  }

  // 3. Resolution check — requires loading the image to read dimensions
  const resolution = await getImageResolution(file);
  const { width, height } = resolution;

  const isTooSmall = width < MIN_RESOLUTION || height < MIN_RESOLUTION;
  const isTooLarge = width > MAX_RESOLUTION || height > MAX_RESOLUTION;

  if (isTooSmall) {
    return {
      valid: false,
      error: {
        code: 'INVALID_RESOLUTION',
        message: `Your photo is too small (${width}×${height} pixels). Please use a photo of at least 200×200 pixels.`,
      },
    };
  }

  if (isTooLarge) {
    return {
      valid: false,
      error: {
        code: 'INVALID_RESOLUTION',
        message: `Your photo is too large (${width}×${height} pixels). Please use a photo no larger than 8000×8000 pixels, or try a lower camera resolution setting.`,
      },
    };
  }

  return { valid: true };
}

/**
 * Loads an image file via an object URL and resolves with its natural dimensions.
 * Revokes the object URL after reading to avoid memory leaks.
 */
function getImageResolution(
  file: File,
): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();

    img.onload = () => {
      const width = img.naturalWidth;
      const height = img.naturalHeight;
      URL.revokeObjectURL(url);
      resolve({ width, height });
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to load image for resolution validation.'));
    };

    img.src = url;
  });
}
