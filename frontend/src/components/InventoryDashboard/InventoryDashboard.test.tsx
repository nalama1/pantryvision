import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { InventoryDashboard } from './InventoryDashboard';
import { LanguageProvider } from '../../i18n/LanguageContext';
import type { InventoryProduct } from '../../services/inventoryService';

// The ProductCard is not exported separately, so exercise its Edit/Delete controls
// THROUGH the InventoryDashboard by mocking listProducts to return one known product
// (no network). Keep the real ListProductsError etc. by spreading the actual module.
vi.mock('../../services/inventoryService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/inventoryService')>();
  return {
    ...actual,
    listProducts: vi.fn(),
  };
});

// EditForm / DeleteConfirmation import manageProductService; mock its side-effecting
// calls so opening an overlay never hits the network. Preserve the real error class.
vi.mock('../../services/manageProductService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/manageProductService')>();
  return {
    ...actual,
    updateProduct: vi.fn(),
    deleteProduct: vi.fn(),
  };
});

import { listProducts } from '../../services/inventoryService';
import { updateProduct, deleteProduct } from '../../services/manageProductService';

const mockListProducts = listProducts as Mock;
const mockUpdateProduct = updateProduct as Mock;
const mockDeleteProduct = deleteProduct as Mock;

// A distinctive productName makes the accessible-name assertions unambiguous.
const sampleProduct: InventoryProduct = {
  productId: 'p-1',
  productName: 'Organic Yogurt',
  brand: 'Acme',
  presentation: '500g tub',
  expirationDate: '2026-05-01',
  imageKey: 'images/p-1.jpg',
  imageUrl: null,
  createdAt: '2025-01-01T00:00:00Z',
  quantity: 3,
  unit: 'pack',
};

function renderDashboard() {
  return render(
    <LanguageProvider>
      <InventoryDashboard />
    </LanguageProvider>,
  );
}

// Renders the dashboard and waits past the loading state until the grid (and thus the
// single product card) is on screen.
async function renderAndWaitForCard() {
  renderDashboard();
  await waitFor(() => expect(screen.getByTestId('inventory-grid')).toBeInTheDocument());
  return within(screen.getByTestId('product-card'));
}

describe('InventoryDashboard ProductCard accessibility', () => {
  beforeEach(() => {
    mockListProducts.mockReset();
    mockListProducts.mockResolvedValue([sampleProduct]);
  });

  // Req 4.1
  it('renders the Edit control as a focusable button with an accessible name including the product name', async () => {
    const card = await renderAndWaitForCard();

    const editBtn = card.getByTestId('edit-product-btn');

    // Real <button> element (keyboard-focusable by default).
    expect(editBtn.tagName).toBe('BUTTON');

    // Focusable: focusing it makes it the active element.
    editBtn.focus();
    expect(document.activeElement).toBe(editBtn);

    // Accessible name is the localized "Edit {name}" and includes the product name.
    expect(editBtn).toHaveAttribute('aria-label', 'Edit Organic Yogurt');
    expect(editBtn.getAttribute('aria-label')).toContain('Organic Yogurt');
  });

  // Req 5.1
  it('renders the Delete control as a focusable button with an accessible name including the product name', async () => {
    const card = await renderAndWaitForCard();

    const deleteBtn = card.getByTestId('delete-product-btn');

    expect(deleteBtn.tagName).toBe('BUTTON');

    deleteBtn.focus();
    expect(document.activeElement).toBe(deleteBtn);

    expect(deleteBtn).toHaveAttribute('aria-label', 'Delete Organic Yogurt');
    expect(deleteBtn.getAttribute('aria-label')).toContain('Organic Yogurt');
  });

  // Req 4.1, 5.1 — both controls are queryable by role with their accessible names.
  it('exposes both controls to assistive tech via role=button with the accessible name', async () => {
    await renderAndWaitForCard();

    expect(screen.getByRole('button', { name: 'Edit Organic Yogurt' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete Organic Yogurt' })).toBeInTheDocument();
  });

  // Optional light integration sanity: activating the controls opens the expected overlay.
  it('opens the edit overlay when the Edit control is activated', async () => {
    const card = await renderAndWaitForCard();

    fireEvent.click(card.getByTestId('edit-product-btn'));

    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());
  });

  it('opens the delete confirmation dialog when the Delete control is activated', async () => {
    const card = await renderAndWaitForCard();

    fireEvent.click(card.getByTestId('delete-product-btn'));

    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());
  });
});

describe('InventoryDashboard success feedback and image preservation', () => {
  beforeEach(() => {
    mockListProducts.mockReset();
    mockUpdateProduct.mockReset();
    mockDeleteProduct.mockReset();
  });

  // Bug 1: after a successful delete, a success toast appears with the deleteSuccess text.
  // The toast is rendered inline in the filters row (beside the "Good" filter), so it is
  // visible as long as at least one product remains. We seed two products and delete one.
  it('shows a success toast after confirming a delete', async () => {
    const second: InventoryProduct = { ...sampleProduct, productId: 'p-2', productName: 'Milk' };
    mockListProducts.mockResolvedValue([sampleProduct, second]);
    mockDeleteProduct.mockResolvedValue(undefined);

    renderDashboard();
    await waitFor(() => expect(screen.getByTestId('inventory-grid')).toBeInTheDocument());

    // Delete the first product's card.
    const firstCard = within(screen.getAllByTestId('product-card')[0]);
    fireEvent.click(firstCard.getByTestId('delete-product-btn'));

    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('delete-confirm-btn'));

    // The inline toast appears (one product remains, so the filters row is still shown).
    const toast = await screen.findByTestId('success-toast');
    // Message now includes the product name, e.g. 'Product "Organic Yogurt" deleted'.
    expect(toast).toHaveTextContent(/Product .*Organic Yogurt.* deleted/);
  });

  // Bug 2: editing preserves the derived presigned imageUrl even though the
  // update-product response does not include it. The card must still show the <img>.
  it('preserves the product image after a successful edit', async () => {
    const productWithImage: InventoryProduct = {
      ...sampleProduct,
      imageUrl: 'https://example.com/presigned/p-1.jpg',
    };
    mockListProducts.mockResolvedValue([productWithImage]);
    // update-product returns the raw record WITHOUT imageUrl (matches real backend).
    mockUpdateProduct.mockResolvedValue({
      productId: 'p-1',
      productName: 'Organic Yogurt Updated',
      brand: 'Acme',
      presentation: '500g tub',
      expirationDate: '2026-05-01',
      imageKey: 'images/p-1.jpg',
      createdAt: '2025-01-01T00:00:00Z',
      quantity: 3,
      unit: 'pack',
    });

    const card = await renderAndWaitForCard();
    // Image is present before editing.
    expect(card.getByRole('img')).toHaveAttribute('src', productWithImage.imageUrl);

    fireEvent.click(card.getByTestId('edit-product-btn'));
    await waitFor(() => expect(screen.getByTestId('edit-form')).toBeInTheDocument());
    fireEvent.submit(screen.getByTestId('edit-form'));

    // After edit success the card still shows the img with the prior presigned URL.
    await waitFor(() =>
      expect(screen.getByText('Organic Yogurt Updated')).toBeInTheDocument(),
    );
    const updatedCard = within(screen.getByTestId('product-card'));
    expect(updatedCard.getByRole('img')).toHaveAttribute('src', productWithImage.imageUrl);
  });
});
