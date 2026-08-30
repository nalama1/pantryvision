import { useState, useCallback, useEffect } from 'react';
import confetti from 'canvas-confetti';
import './styles/App.css';
import { PhotoUploader } from './components/PhotoUploader';
import { ReviewForm, requestExtraction } from './components/ReviewForm';
import type { ExtractionResult, ProductData } from './components/ReviewForm';
import type { UploadError } from './components/PhotoUploader';
import { saveProduct } from './services/productService';
import { NavBar } from './components/NavBar';
import type { AppView } from './components/NavBar';
import { InventoryDashboard } from './components/InventoryDashboard';
import { useLanguage } from './i18n/LanguageContext';

type AppState = 'upload' | 'extracting' | 'review' | 'done';

// Fallback result used when AI extraction is skipped or fails.
// The error text here is internal-only (never rendered — ReviewForm shows its own
// translated extractionError message when extractionResult.error is set).
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
  const { t } = useLanguage();
  const [view, setView] = useState<AppView>('upload');
  const [appState, setAppState] = useState<AppState>('upload');
  const [extractionResult, setExtractionResult] = useState<ExtractionResult | null>(null);
  const [confirmedProduct, setConfirmedProduct] = useState<ProductData | null>(null);
  const [objectKey, setObjectKey] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0);

  // Rotate the friendly loading message while AI extraction is in progress.
  useEffect(() => {
    if (appState !== 'extracting') return;

    const intervalId = setInterval(() => {
      setLoadingMessageIndex((prev) => (prev + 1) % 3);
    }, 2200);

    return () => clearInterval(intervalId);
  }, [appState]);

  // Celebrate a successful save with a brief, tasteful gold confetti burst.
  useEffect(() => {
    if (appState === 'done') {
      confetti({
        particleCount: 60,
        spread: 70,
        origin: { y: 0.6 },
        colors: ['#E6AF2E', '#F0BE45', '#0077B6', '#FFFFFF'],
        disableForReducedMotion: true,
      });
    }
  }, [appState]);

  const handleUploadComplete = useCallback(async (objectKey: string) => {
    setObjectKey(objectKey);
    setLoadingMessageIndex(0);
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
        <h1 className="app-header__title">Pantry Vision</h1>
      </header>

      <NavBar activeView={view} onSelectView={setView} />

      <main className={`app-main ${view === 'inventory' ? 'app-main--full' : ''}`}>
        {view === 'upload' && (
          <>
            {appState === 'upload' && (
              <div className="app-section">
                <h2>{t('photoUploader.title')}</h2>
                <PhotoUploader
                  onUploadComplete={handleUploadComplete}
                  onError={handleUploadError}
                />
                <p className="app-section__help-text">{t('photoUploader.helpText')}</p>
              </div>
            )}

            {appState === 'extracting' && (
              <div className="app-section">
                <div className="app-extracting" data-testid="extracting-state">
                  <h2>{t('extracting.title')}</h2>
                  <div
                    className="spinner"
                    data-testid="loading-indicator"
                    role="status"
                    aria-label="Loading"
                  ></div>
                  {(() => {
                    const rotatingMessages = [
                      t('extracting.rotatingMessage1'),
                      t('extracting.rotatingMessage2'),
                      t('extracting.rotatingMessage3'),
                    ];
                    return (
                      <p
                        className="app-extracting__message"
                        key={loadingMessageIndex}
                        data-testid="extracting-message"
                      >
                        {rotatingMessages[loadingMessageIndex % rotatingMessages.length]}
                      </p>
                    );
                  })()}
                  <button
                    className="btn btn--secondary"
                    data-testid="skip-extraction-btn"
                    onClick={handleSkipExtraction}
                  >
                    {t('extracting.skipButton')}
                  </button>
                </div>
              </div>
            )}

            {appState === 'review' && extractionResult && (
              <section className="app-section">
                <h2 className="app-section__title">{t('reviewForm.title')}</h2>
                {saving && (
                  <div className="app-extracting" data-testid="saving-state">
                    <div className="spinner" role="status" aria-label="Saving"></div>
                    <p className="app-extracting__message">{t('saving.message')}</p>
                  </div>
                )}
                {saveError && (
                  <div className="photo-uploader__error" role="alert" data-testid="save-error">
                    <p>{saveError}</p>
                    <button className="btn btn--secondary" onClick={() => setSaveError(null)}>
                      {t('saving.dismiss')}
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
                      {t('done.message', { name: confirmedProduct.productName })}
                    </p>
                    <button
                      className="btn btn--primary"
                      data-testid="upload-another-btn"
                      onClick={handleUploadAnother}
                    >
                      {t('done.uploadAnother')}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {view === 'inventory' && (
          <div className="app-section">
            <InventoryDashboard />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
