export type ConfidenceLevel = 'high' | 'medium' | 'low';

export interface ExtractionResult {
  productName: string | null;
  brand: string | null;
  presentation: string | null;
  expirationDate: string | null; // ISO 8601 YYYY-MM-DD
  confidence: {
    productName: ConfidenceLevel;
    brand: ConfidenceLevel;
    presentation: ConfidenceLevel;
    expirationDate: ConfidenceLevel;
  };
  error?: string; // Present when AI extraction failed
}

export interface ProductData {
  productName: string;
  brand: string;
  presentation: string;
  expirationDate: string;
}

export interface ReviewFormProps {
  extractionResult: ExtractionResult;
  onConfirm: (data: ProductData) => void;
  onCancel: () => void;
}
