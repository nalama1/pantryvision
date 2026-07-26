import { useState, useCallback } from 'react';
import './styles/App.css';
import { PhotoUploader } from './components/PhotoUploader';
import { ReviewForm, requestExtraction } from './components/ReviewForm';
import type { ExtractionResult, ProductData } from './components/ReviewForm';
import type { UploadError } from './components/PhotoUploader';
import { saveProduct } from './services/productService';

type AppState = 'upload' | 'extracting' | 'review' | 'done';

// Fallback result used when AI extraction is skipped or fails
const FALLBACK_EXTRACTION_RESULT: ExtractionResult = {
  productName: null,
  brand: null,
  presentation: null,
  expirationDate: null,
  confidence: {
    productName: 'low',
    brand: 'low',
    presentation: 'low',
    expirationDate: 'low',
  },
  error: 'Extraction skipped. Please fill in the details manually.',
};

function App() {
  const [appState, setAppState] = useState<AppState>('upload');
  const [extractionResult, setExtractionResult] = useState<ExtractionResult | null>(null);
  const [confirmedProduct, setConfirmedProduct] = useState<ProductData | null>(null);
  const [objectKey, setObjectKey] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleUploadComplete = useCallback(async (objectKey: string) => {
    setObjectKey(objectKey);
    setAppState('extracting');

    try {
      const result = await requestExtraction(objectKey);
      setExtractionResult(result);
    } catch {
      // AI never blocks: on any error, show ReviewForm with all-null fields
      setExtractionResult({
        ...FALLBACK_EXTRACTION_RESULT,
        error: 'Extraction failed. Please fill in the details manually.',
      });
    }

    setAppState('review');
  }, []);

  const handleUploadError = useCallback((error: UploadError) => {
    console.error('Upload error:', error.code, error.message);
  }, []);

  const handleConfirm = useCallback(async (data: ProductData) => {
    if (!objectKey) return;

    setSaving(true);
    setSaveError(null);

    try {
      const result = await saveProduct({
        productName: data.productName,
        brand: data.brand,
        presentation: data.presentation,
        expirationDate: data.expirationDate,
        imageKey: objectKey,
      });

      console.log('Product saved:', result);
      setConfirmedProduct(data);
      setAppState('done');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save product';
      setSaveError(message);
    } finally {
      setSaving(false);
    }
  }, [objectKey]);

  const handleCancel = useCallback(() => {
    setExtractionResult(null);
    setObjectKey(null);
    setSaveError(null);
    setAppState('upload');
  }, []);

  const handleUploadAnother = useCallback(() => {
    setExtractionResult(null);
    setConfirmedProduct(null);
    setObjectKey(null);
    setSaveError(null);
    setAppState('upload');
  }, []);

  // Skip extraction and go straight to manual entry
  const handleSkipExtraction = useCallback(() => {
    setExtractionResult(FALLBACK_EXTRACTION_RESULT);
    setAppState('review');
  }, []);

  return (
    <div>
      <header className="app-header">
        <h1 className="app-header__title">PantryVision</h1>
      </header>

      <main className="app-main">
        {appState === 'upload' && (
          <div className="app-section">
            <h2>Upload Product Photo</h2>
            <PhotoUploader
              onUploadComplete={handleUploadComplete}
              onError={handleUploadError}
            />
          </div>
        )}

        {appState === 'extracting' && (
          <div className="app-section">
            <div className="app-extracting" data-testid="extracting-state">
              <h2>Extracting product data...</h2>
              <div
                className="spinner"
                data-testid="loading-indicator"
                role="status"
                aria-label="Loading"
              ></div>
              <p className="app-extracting__message">Please wait while AI analyzes the image.</p>
              <button
                className="btn btn--secondary"
                data-testid="skip-extraction-btn"
                onClick={handleSkipExtraction}
              >
                Skip to manual entry
              </button>
            </div>
          </div>
        )}

        {appState === 'review' && extractionResult && (
          <section className="app-section">
            <h2 className="app-section__title">Review Product Data</h2>
            {saving && (
              <div className="app-extracting" data-testid="saving-state">
                <div className="spinner" role="status" aria-label="Saving"></div>
                <p className="app-extracting__message">Saving product to inventory...</p>
              </div>
            )}
            {saveError && (
              <div className="photo-uploader__error" role="alert" data-testid="save-error">
                <p>{saveError}</p>
                <button className="btn btn--secondary" onClick={() => setSaveError(null)}>
                  Dismiss
                </button>
              </div>
            )}
            <ReviewForm
              extractionResult={extractionResult}
              onConfirm={handleConfirm}
              onCancel={handleCancel}
            />
          </section>
        )}

        {appState === 'done' && confirmedProduct && (
          <div className="app-section">
            <div className="app-done" data-testid="done-state">
              <div className="app-done__card">
                <div className="app-done__icon">✅</div>
                <p className="app-done__message">
                  Product &quot;<span className="app-done__product-name">{confirmedProduct.productName}</span>&quot; has been registered.
                </p>
                <button
                  className="btn btn--primary"
                  data-testid="upload-another-btn"
                  onClick={handleUploadAnother}
                >
                  Upload Another
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
