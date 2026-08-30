import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { DeleteConfirmation } from './DeleteConfirmation';
import { LanguageProvider } from '../../i18n/LanguageContext';
import type { InventoryProduct } from '../../services/inventoryService';

// Mock the service while preserving the real ManageProductError class, so error-path
// tests can construct genuine ManageProductError instances (code + message) and the
// component's `err instanceof ManageProductError` check behaves exactly as in prod.
vi.mock('../../services/manageProductService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/manageProductService')>();
  return {
    ...actual,
    deleteProduct: vi.fn(),
  };
});

import { deleteProduct, ManageProductError } from '../../services/manageProductService';

const mockDeleteProduct = deleteProduct as Mock;

const sampleProduct: InventoryProduct = {
  productId: 'prod-123',
  productName: 'Whole Milk',
  brand: 'Acme',
  presentation: '1L carton',
  expirationDate: '2026-01-01',
  imageKey: 'images/prod-123.jpg',
  imageUrl: null,
  createdAt: '2025-01-01T00:00:00Z',
  quantity: 2,
  unit: 'pack',
};

function renderDialog(overrides?: {
  onConfirmed?: (productId: string) => void;
  onCancel?: () => void;
}) {
  const onConfirmed = overrides?.onConfirmed ?? vi.fn();
  const onCancel = overrides?.onCancel ?? vi.fn();

  const utils = render(
    <LanguageProvider>
      <DeleteConfirmation
        product={sampleProduct}
        onConfirmed={onConfirmed}
        onCancel={onCancel}
      />
    </LanguageProvider>,
  );

  return { ...utils, onConfirmed, onCancel };
}

describe('DeleteConfirmation', () => {
  beforeEach(() => {
    mockDeleteProduct.mockReset();
  });

  // Req 5.2, 5.3
  it('opens as a modal dialog naming the product with valid aria references', () => {
    renderDialog();

    const dialog = screen.getByTestId('delete-confirm-dialog');
    expect(dialog).toHaveAttribute('role', 'dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');

    // The product name must appear in the confirmation message (Req 5.2).
    expect(screen.getByText(/Whole Milk/)).toBeInTheDocument();

    // aria-labelledby / aria-describedby must point at elements that actually exist.
    const labelId = dialog.getAttribute('aria-labelledby');
    const describedId = dialog.getAttribute('aria-describedby');
    expect(labelId).toBeTruthy();
    expect(describedId).toBeTruthy();
    expect(document.getElementById(labelId as string)).toBeInTheDocument();
    const describedEl = document.getElementById(describedId as string);
    expect(describedEl).toBeInTheDocument();
    expect(describedEl).toHaveTextContent(/Whole Milk/);
  });

  // Req 5.2 — focus moves into the dialog on open (component focuses Cancel in a useEffect).
  it('moves focus to the Cancel button on open', async () => {
    renderDialog();

    const cancelBtn = screen.getByTestId('delete-cancel-btn');
    await waitFor(() => expect(document.activeElement).toBe(cancelBtn));
  });

  // Req 5.3 — focus trap: Tab from the last control wraps to the first, and
  // Shift+Tab from the first wraps to the last. The handler calls preventDefault + focus.
  it('traps focus by cycling between Cancel and Confirm', () => {
    renderDialog();

    const dialog = screen.getByTestId('delete-confirm-dialog');
    const cancelBtn = screen.getByTestId('delete-cancel-btn');
    const confirmBtn = screen.getByTestId('delete-confirm-btn');

    // Tab from the last focusable (Confirm) should wrap to the first (Cancel).
    confirmBtn.focus();
    expect(document.activeElement).toBe(confirmBtn);
    fireEvent.keyDown(dialog, { key: 'Tab' });
    expect(document.activeElement).toBe(cancelBtn);

    // Shift+Tab from the first focusable (Cancel) should wrap to the last (Confirm).
    cancelBtn.focus();
    expect(document.activeElement).toBe(cancelBtn);
    fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(confirmBtn);
  });

  // Req 5.5 — Cancel closes with no delete call.
  it('cancels without deleting when Cancel is clicked', () => {
    const { onCancel } = renderDialog();

    fireEvent.click(screen.getByTestId('delete-cancel-btn'));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(mockDeleteProduct).not.toHaveBeenCalled();
  });

  // Req 5.5 — Escape cancels the dialog.
  it('cancels when Escape is pressed', () => {
    const { onCancel } = renderDialog();

    fireEvent.keyDown(screen.getByTestId('delete-confirm-dialog'), { key: 'Escape' });

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(mockDeleteProduct).not.toHaveBeenCalled();
  });

  // Req 5.5 — focus returns to the opener on close. The component captures
  // document.activeElement at mount as the opener, so we focus a trigger button first.
  it('returns focus to the opener element on cancel', async () => {
    const opener = document.createElement('button');
    opener.setAttribute('data-testid', 'opener');
    document.body.appendChild(opener);
    opener.focus();
    expect(document.activeElement).toBe(opener);

    renderDialog();
    // The mount effect steals focus to Cancel; cancelling should restore it to the opener.
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByTestId('delete-cancel-btn')),
    );

    fireEvent.click(screen.getByTestId('delete-cancel-btn'));
    expect(document.activeElement).toBe(opener);

    document.body.removeChild(opener);
  });

  // Req 5.6 — confirm shows a loading label and disables both controls while in flight.
  it('shows loading and disables controls while deleting', async () => {
    // Controlled promise that we never resolve, to freeze the in-flight state.
    let resolveFn: (value: { productId: string }) => void = () => {};
    const pending = new Promise<{ productId: string }>((resolve) => {
      resolveFn = resolve;
    });
    mockDeleteProduct.mockReturnValue(pending);

    renderDialog();

    const cancelBtn = screen.getByTestId('delete-cancel-btn');
    const confirmBtn = screen.getByTestId('delete-confirm-btn');

    fireEvent.click(confirmBtn);

    await waitFor(() => expect(confirmBtn).toBeDisabled());
    expect(cancelBtn).toBeDisabled();
    // Confirm label switches to the "Deleting…" text (deleteConfirmation.deleting).
    expect(confirmBtn).toHaveTextContent('Deleting…');

    // Cleanly resolve so no unhandled promise lingers.
    resolveFn({ productId: sampleProduct.productId });
  });

  // Req 5.7 — success invokes onConfirmed with the productId (parent removes the card).
  it('calls onConfirmed with the productId on success', async () => {
    mockDeleteProduct.mockResolvedValue({ productId: sampleProduct.productId });

    const { onConfirmed } = renderDialog();

    fireEvent.click(screen.getByTestId('delete-confirm-btn'));

    await waitFor(() =>
      expect(onConfirmed).toHaveBeenCalledWith(sampleProduct.productId),
    );
    expect(screen.queryByTestId('delete-error')).not.toBeInTheDocument();
  });

  // Req 5.8 — a backend error keeps the card, shows an error banner, and re-enables controls.
  it('shows an error and re-enables controls when delete fails (INTERNAL_ERROR)', async () => {
    mockDeleteProduct.mockRejectedValue(new ManageProductError('INTERNAL_ERROR', 'boom'));

    const { onConfirmed } = renderDialog();

    fireEvent.click(screen.getByTestId('delete-confirm-btn'));

    const errorBanner = await screen.findByTestId('delete-error');
    expect(errorBanner).toBeInTheDocument();
    expect(errorBanner).toHaveTextContent('boom');

    expect(onConfirmed).not.toHaveBeenCalled();
    expect(screen.getByTestId('delete-cancel-btn')).not.toBeDisabled();
    expect(screen.getByTestId('delete-confirm-btn')).not.toBeDisabled();
  });

  // Req 5.8 — a client-side timeout is treated identically to a backend failure.
  it('shows an error and re-enables controls on TIMEOUT', async () => {
    mockDeleteProduct.mockRejectedValue(
      new ManageProductError('TIMEOUT', 'Request timed out'),
    );

    const { onConfirmed } = renderDialog();

    fireEvent.click(screen.getByTestId('delete-confirm-btn'));

    const errorBanner = await screen.findByTestId('delete-error');
    expect(errorBanner).toBeInTheDocument();
    expect(errorBanner).toHaveTextContent('Request timed out');

    expect(onConfirmed).not.toHaveBeenCalled();
    expect(screen.getByTestId('delete-cancel-btn')).not.toBeDisabled();
    expect(screen.getByTestId('delete-confirm-btn')).not.toBeDisabled();
  });
});
