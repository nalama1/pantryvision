import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { EditForm } from './EditForm';
import { LanguageProvider } from '../../i18n/LanguageContext';
import { ManageProductError } from '../../services/manageProductService';
import { updateProduct } from '../../services/manageProductService';
import type { InventoryProduct } from '../../services/inventoryService';

// Mock only updateProduct while preserving the real ManageProductError class, so the
// component's `err instanceof ManageProductError` branch still works in the error test.
vi.mock('../../services/manageProductService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/manageProductService')>();
  return {
    ...actual,
    updateProduct: vi.fn(),
  };
});

const mockUpdateProduct = vi.mocked(updateProduct);

// Sample product with known editable + preserved values used to pre-fill the form.
const sampleProduct: InventoryProduct = {
  productId: 'prod-123',
  productName: 'Whole Milk',
  brand: 'Alpura',
  presentation: '1 L carton',
  expirationDate: '2026-07-27',
  imageKey: 'images/prod-123.jpg',
  imageUrl: 'https://example.com/prod-123.jpg',
  createdAt: '2026-01-01T00:00:00Z',
  quantity: 2,
  unit: 'pack',
};

function renderEditForm(overrides?: Partial<InventoryProduct>) {
  const onSuccess = vi.fn();
  const onCancel = vi.fn();
  const product = { ...sampleProduct, ...overrides };
  render(
    <LanguageProvider>
      <EditForm product={product} onSuccess={onSuccess} onCancel={onCancel} />
    </LanguageProvider>,
  );
  return { onSuccess, onCancel, product };
}

describe('EditForm', () => {
  beforeEach(() => {
    mockUpdateProduct.mockReset();
  });

  // Req 4.2: form is pre-filled with the product's current editable values.
  it('pre-fills the inputs with the product current values', () => {
    renderEditForm();

    expect(screen.getByTestId('edit-field-productName')).toHaveValue('Whole Milk');
    expect(screen.getByTestId('edit-field-brand')).toHaveValue('Alpura');
    expect(screen.getByTestId('edit-field-presentation')).toHaveValue('1 L carton');
    expect(screen.getByTestId('edit-field-expirationDate')).toHaveValue('2026-07-27');
  });

  // Req 4.7: whitespace-only productName blocks submit, shows the required message,
  // and retains the other user-entered values.
  it('blocks submit and shows a message when productName is whitespace-only, retaining values', () => {
    renderEditForm();

    const nameInput = screen.getByTestId('edit-field-productName');
    const brandInput = screen.getByTestId('edit-field-brand');

    fireEvent.change(nameInput, { target: { value: '   ' } });
    fireEvent.change(brandInput, { target: { value: 'New Brand' } });
    fireEvent.click(screen.getByTestId('edit-submit-btn'));

    expect(mockUpdateProduct).not.toHaveBeenCalled();

    const fieldError = screen.getByTestId('edit-error-productName');
    expect(fieldError).toBeInTheDocument();
    expect(fieldError).toHaveTextContent('Product name is required.');

    // Entered values must be retained.
    expect(screen.getByTestId('edit-field-brand')).toHaveValue('New Brand');
    expect(screen.getByTestId('edit-field-productName')).toHaveValue('   ');
  });

  // Req 4.8: productName longer than 200 chars blocks submit and shows the length message.
  it('blocks submit and shows the length message when productName exceeds 200 chars', () => {
    renderEditForm();

    const longName = 'a'.repeat(201);
    fireEvent.change(screen.getByTestId('edit-field-productName'), {
      target: { value: longName },
    });
    fireEvent.click(screen.getByTestId('edit-submit-btn'));

    expect(mockUpdateProduct).not.toHaveBeenCalled();

    const fieldError = screen.getByTestId('edit-error-productName');
    expect(fieldError).toBeInTheDocument();
    expect(fieldError).toHaveTextContent('Product name must be 200 characters or fewer.');
  });

  // Req 4.5: a successful update resolves the updated record and calls onSuccess with it.
  it('calls onSuccess with the resolved record when the update succeeds', async () => {
    const updatedRecord: InventoryProduct = {
      ...sampleProduct,
      productName: 'Skim Milk',
      brand: 'Lala',
    };
    mockUpdateProduct.mockResolvedValueOnce(updatedRecord);

    const { onSuccess } = renderEditForm();

    fireEvent.change(screen.getByTestId('edit-field-productName'), {
      target: { value: 'Skim Milk' },
    });
    fireEvent.change(screen.getByTestId('edit-field-brand'), {
      target: { value: 'Lala' },
    });
    fireEvent.click(screen.getByTestId('edit-submit-btn'));

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(updatedRecord);
    });
    expect(mockUpdateProduct).toHaveBeenCalledTimes(1);
  });

  // Req 4.6: on error the form stays open, values are retained, onSuccess is not called,
  // an error banner shows, and the submit button is re-enabled.
  it('keeps the form open, retains values, and re-enables submit when the update fails', async () => {
    mockUpdateProduct.mockRejectedValueOnce(
      new ManageProductError('INTERNAL_ERROR', 'boom'),
    );

    const { onSuccess } = renderEditForm();

    fireEvent.change(screen.getByTestId('edit-field-productName'), {
      target: { value: 'Skim Milk' },
    });
    fireEvent.change(screen.getByTestId('edit-field-brand'), {
      target: { value: 'Lala' },
    });
    fireEvent.click(screen.getByTestId('edit-submit-btn'));

    // Error banner appears.
    await waitFor(() => {
      expect(screen.getByTestId('edit-error')).toBeInTheDocument();
    });
    expect(screen.getByTestId('edit-error')).toHaveTextContent('boom');

    // onSuccess must not have been called.
    expect(onSuccess).not.toHaveBeenCalled();

    // Entered values retained.
    expect(screen.getByTestId('edit-field-productName')).toHaveValue('Skim Milk');
    expect(screen.getByTestId('edit-field-brand')).toHaveValue('Lala');

    // Submit re-enabled after the failure.
    await waitFor(() => {
      expect(screen.getByTestId('edit-submit-btn')).toBeEnabled();
    });
  });

  // Req 4.x (affordance): the cancel control invokes onCancel.
  it('calls onCancel when the cancel button is clicked', () => {
    const { onCancel } = renderEditForm();

    fireEvent.click(screen.getByTestId('edit-cancel-btn'));

    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
