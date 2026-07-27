import { useState, useRef, useCallback, useEffect } from 'react';
import './PhotoUploader.css';
import { validateFile, type UploadError } from './validateFile';
import { requestPresignedUrl, uploadToS3, UploadServiceError } from './uploadService';
import { useLanguage } from '../../i18n/LanguageContext';

export type UploadState = 'idle' | 'previewing' | 'uploading' | 'success' | 'error';

export interface PhotoUploaderProps {
  onUploadComplete: (objectKey: string) => void;
  onError?: (error: UploadError) => void;
}

const MAX_RETRIES = 3;
const BACKOFF_DELAYS_MS = [1000, 2000, 4000]; // Exponential backoff: 1s, 2s, 4s

/** Helper to delay execution for exponential backoff */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * PhotoUploader handles file selection (gallery and camera), client-side validation,
 * image preview, presigned URL request, direct-to-S3 upload with progress tracking,
 * and automatic retry logic with exponential backoff.
 */
export function PhotoUploader({ onUploadComplete, onError }: PhotoUploaderProps) {
  const { t } = useLanguage();
  const [state, setState] = useState<UploadState>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [retryCount, setRetryCount] = useState<number>(0);
  const [presignRetried, setPresignRetried] = useState<boolean>(false);
  const [errorInfo, setErrorInfo] = useState<UploadError | null>(null);
  const [cameraAvailable, setCameraAvailable] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  // Check camera availability on mount via navigator.mediaDevices
  useEffect(() => {
    const checkCamera = async () => {
      try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
          setCameraAvailable(false);
          return;
        }
        const devices = await navigator.mediaDevices.enumerateDevices();
        const hasCamera = devices.some((device) => device.kind === 'videoinput');
        setCameraAvailable(hasCamera);
      } catch {
        // Camera access denied or unavailable
        setCameraAvailable(false);
      }
    };

    checkCamera();
  }, []);

  const resetState = useCallback(() => {
    setState('idle');
    setSelectedFile(null);
    setPreviewUrl(null);
    setUploadProgress(0);
    setRetryCount(0);
    setPresignRetried(false);
    setErrorInfo(null);
  }, []);

  /** Shared file processing logic used by both file input and drag-and-drop */
  const processFile = useCallback(
    async (file: File) => {
      const result = await validateFile(file);

      if (!result.valid) {
        setState('error');
        setErrorInfo(result.error);
        onError?.(result.error);
        return;
      }

      // Validation passed — transition to previewing state
      const objectUrl = URL.createObjectURL(file);
      setSelectedFile(file);
      setPreviewUrl(objectUrl);
      setErrorInfo(null);
      setUploadProgress(0);
      setRetryCount(0);
      setPresignRetried(false);
      setState('previewing');
    },
    [onError],
  );

  const handleFileChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];

      // User cancelled file selection — stay in idle, no error
      if (!file) {
        return;
      }

      await processFile(file);

      // Reset file input so the same file can be re-selected if needed
      event.target.value = '';
    },
    [processFile],
  );

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      processFile(file);
    }
  }, [processFile]);

  const handleSelectFromGallery = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleCaptureFromCamera = useCallback(() => {
    cameraInputRef.current?.click();
  }, []);

  const handleCancelPreview = useCallback(() => {
    // Revoke object URL to prevent memory leaks
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    resetState();
  }, [previewUrl, resetState]);

  const handleConfirmUpload = useCallback(async () => {
    if (!selectedFile) return;

    setState('uploading');
    setUploadProgress(0);

    const fileExtension =
      selectedFile.name.split('.').pop()?.toLowerCase() ||
      selectedFile.type.split('/')[1];

    let currentRetryCount = 0;
    let hasPresignRetried = false;

    // Attempt to upload with retry logic
    while (true) {
      try {
        // Step 1: Request presigned URL from backend
        const { uploadUrl, objectKey } = await requestPresignedUrl(
          selectedFile.type,
          fileExtension,
        );

        // Step 2: Upload file directly to S3 with progress tracking and 30s timeout
        await uploadToS3(selectedFile, uploadUrl, (percent) => {
          setUploadProgress(percent);
        });

        // Step 3: Success — notify parent component
        setUploadProgress(100);
        setRetryCount(currentRetryCount);
        setPresignRetried(hasPresignRetried);
        setState('success');
        onUploadComplete(objectKey);
        return;
      } catch (err) {
        // Classify the error and decide on retry strategy
        if (err instanceof UploadServiceError) {
          if (err.code === 'PRESIGN_EXPIRED' && !hasPresignRetried) {
            // Presigned URL expired — request a new one and retry once
            hasPresignRetried = true;
            setPresignRetried(true);
            try {
              const { uploadUrl: newUrl, objectKey } = await requestPresignedUrl(
                selectedFile.type,
                fileExtension,
              );
              await uploadToS3(selectedFile, newUrl, (percent) => {
                setUploadProgress(percent);
              });

              // Retry succeeded
              setUploadProgress(100);
              setRetryCount(currentRetryCount);
              setState('success');
              onUploadComplete(objectKey);
              return;
            } catch (retryErr) {
              // Presign retry also failed — show final error
              const error: UploadError = {
                code: 'PRESIGN_FAILED',
                message: t('photoUploader.errorPresignFailed'),
              };
              setErrorInfo(error);
              setRetryCount(currentRetryCount);
              setState('error');
              onError?.(error);
              return;
            }
          }

          if (err.code === 'TIMEOUT') {
            // Timeout — do not auto-retry, show error with manual retry option
            const error: UploadError = {
              code: 'TIMEOUT',
              message: t('photoUploader.errorTimeout'),
            };
            setErrorInfo(error);
            setRetryCount(currentRetryCount);
            setPresignRetried(hasPresignRetried);
            setState('error');
            onError?.(error);
            return;
          }

          if (err.code === 'NETWORK_ERROR') {
            // Network error — retry with exponential backoff up to MAX_RETRIES
            if (currentRetryCount < MAX_RETRIES) {
              const backoffMs = BACKOFF_DELAYS_MS[currentRetryCount];
              currentRetryCount++;
              setRetryCount(currentRetryCount);
              await delay(backoffMs);
              // Loop continues to retry
              continue;
            }

            // Max retries exhausted — show final error
            const error: UploadError = {
              code: 'NETWORK_ERROR',
              message: t('photoUploader.errorNetworkExhausted'),
            };
            setErrorInfo(error);
            setRetryCount(currentRetryCount);
            setPresignRetried(hasPresignRetried);
            setState('error');
            onError?.(error);
            return;
          }

          // Presign expired but already retried — show final error
          if (err.code === 'PRESIGN_EXPIRED' && hasPresignRetried) {
            const error: UploadError = {
              code: 'PRESIGN_FAILED',
              message: t('photoUploader.errorPresignRepeated'),
            };
            setErrorInfo(error);
            setRetryCount(currentRetryCount);
            setState('error');
            onError?.(error);
            return;
          }
        }

        // Generic/unexpected error — treat as network error for retry
        if (currentRetryCount < MAX_RETRIES) {
          const backoffMs = BACKOFF_DELAYS_MS[currentRetryCount];
          currentRetryCount++;
          setRetryCount(currentRetryCount);
          await delay(backoffMs);
          continue;
        }

        // All retries exhausted for unknown error
        const error: UploadError = {
          code: 'NETWORK_ERROR',
          message:
            err instanceof Error
              ? err.message
              : t('photoUploader.errorGeneric'),
        };
        setErrorInfo(error);
        setRetryCount(currentRetryCount);
        setPresignRetried(hasPresignRetried);
        setState('error');
        onError?.(error);
        return;
      }
    }
  }, [selectedFile, onUploadComplete, onError]);

  /** Retry the upload without resetting file selection (for network/timeout errors) */
  const handleRetryUpload = useCallback(() => {
    setRetryCount(0);
    setPresignRetried(false);
    setErrorInfo(null);
    handleConfirmUpload();
  }, [handleConfirmUpload]);

  const handlePreviewError = useCallback(() => {
    // Preview image failed to render — revoke URL and show error
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    const error: UploadError = {
      code: 'PREVIEW_FAILED',
      message: t('photoUploader.errorPreviewFailed'),
    };
    setPreviewUrl(null);
    setSelectedFile(null);
    setErrorInfo(error);
    setState('error');
    onError?.(error);
  }, [previewUrl, onError]);

  const handleDismissError = useCallback(() => {
    resetState();
  }, [resetState]);

  /** Determine if the error is retryable (network/timeout/presign, not file validation) */
  const isRetryableError = errorInfo
    && (errorInfo.code === 'NETWORK_ERROR' || errorInfo.code === 'TIMEOUT' || errorInfo.code === 'PRESIGN_FAILED')
    && selectedFile !== null;

  return (
    <div className="photo-uploader" data-testid="photo-uploader">
      {/* Hidden file inputs */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={handleFileChange}
        style={{ display: 'none' }}
        data-testid="file-input"
        aria-label="Select image from gallery"
      />
      {cameraAvailable && (
        <input
          ref={cameraInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          onChange={handleFileChange}
          style={{ display: 'none' }}
          data-testid="camera-input"
          aria-label="Capture photo with camera"
        />
      )}

      {/* Idle state — show selection options */}
      {state === 'idle' && (
        <div
          className={`photo-uploader__dropzone ${isDragOver ? 'photo-uploader__dropzone--dragover' : ''}`}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          data-testid="idle-state"
        >
          <div className="photo-uploader__icon">📸</div>
          <p className="photo-uploader__text">{t('photoUploader.dropzoneText')}</p>
          <div className="photo-uploader__actions">
            {cameraAvailable && (
              <button
                className="photo-uploader__btn-camera"
                type="button"
                onClick={handleCaptureFromCamera}
                data-testid="capture-camera-btn"
              >
                {t('photoUploader.takePhoto')}
              </button>
            )}
            <button
              className="photo-uploader__btn-gallery"
              type="button"
              onClick={handleSelectFromGallery}
              data-testid="select-gallery-btn"
            >
              {t('photoUploader.selectGallery')}
            </button>
          </div>
        </div>
      )}

      {/* Previewing state — shows image preview with confirm/cancel actions */}
      {state === 'previewing' && (
        <div className="photo-uploader__preview" data-testid="preview-state">
          {previewUrl && (
            <img
              className="photo-uploader__preview-image"
              src={previewUrl}
              alt="Selected image preview"
              onError={handlePreviewError}
              data-testid="preview-image"
            />
          )}
          <div className="photo-uploader__preview-actions">
            <button
              className="btn btn--secondary"
              type="button"
              onClick={handleCancelPreview}
              data-testid="cancel-btn"
            >
              {t('photoUploader.cancel')}
            </button>
            <button
              className="btn btn--primary"
              type="button"
              onClick={handleConfirmUpload}
              data-testid="confirm-btn"
            >
              {t('photoUploader.upload')}
            </button>
          </div>
        </div>
      )}

      {/* Uploading state — buttons disabled while upload is in progress */}
      {state === 'uploading' && (
        <div className="photo-uploader__preview" data-testid="uploading-state">
          {previewUrl && (
            <img
              className="photo-uploader__preview-image"
              src={previewUrl}
              alt="Selected image preview"
              data-testid="preview-image"
            />
          )}
          <div
            className="photo-uploader__progress"
            role="progressbar"
            aria-valuenow={uploadProgress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Upload progress"
            data-testid="progress-bar"
          >
            <div
              className="photo-uploader__progress-fill"
              style={{ width: `${uploadProgress}%` }}
              data-testid="progress-fill"
            />
            <span className="photo-uploader__progress-text" data-testid="progress-text">
              {uploadProgress}%
            </span>
          </div>
          {retryCount > 0 && (
            <p className="photo-uploader__retry-info" data-testid="retry-info">
              {t('photoUploader.retryingInfo', { current: retryCount, max: MAX_RETRIES })}
              {presignRetried && t('photoUploader.refreshingUrl')}
            </p>
          )}
          <div className="photo-uploader__preview-actions">
            <button
              className="btn btn--secondary"
              type="button"
              disabled
              data-testid="cancel-btn"
            >
              {t('photoUploader.cancel')}
            </button>
            <button
              className="btn btn--primary"
              type="button"
              disabled
              data-testid="confirm-btn"
            >
              {t('photoUploader.uploading')}
            </button>
          </div>
        </div>
      )}

      {/* Success state — confirmation message */}
      {state === 'success' && (
        <div className="photo-uploader__success" data-testid="success-state">
          <p data-testid="success-message">{t('photoUploader.uploadSuccess')}</p>
          <button
            className="btn btn--primary"
            type="button"
            onClick={resetState}
            data-testid="new-upload-btn"
          >
            {t('photoUploader.uploadAnother')}
          </button>
        </div>
      )}

      {/* Error state — show error message with appropriate actions */}
      {state === 'error' && errorInfo && (
        <div className="photo-uploader__error" data-testid="error-state" role="alert">
          <p data-testid="error-message">{errorInfo.message}</p>
          <div className="photo-uploader__error-actions">
            {isRetryableError && (
              <button
                className="btn btn--primary"
                type="button"
                onClick={handleRetryUpload}
                data-testid="retry-upload-btn"
              >
                {t('photoUploader.retryUpload')}
              </button>
            )}
            <button
              className="btn btn--secondary"
              type="button"
              onClick={handleDismissError}
              data-testid="dismiss-error-btn"
            >
              {t('photoUploader.tryAgain')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
