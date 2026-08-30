/**
 * Service tests for manageProductService (updateProduct, deleteProduct).
 *
 * Module-load env-var capture:
 * manageProductService reads `const apiEndpoint = import.meta.env.VITE_MANAGE_API_ENDPOINT`
 * at MODULE LOAD time. To make the capture deterministic we DO NOT import the service
 * statically. Instead each test stubs the env with `vi.stubEnv` first (in beforeEach,
 * before any import) and then loads a FRESH copy of the module via dynamic
 * `await import('./manageProductService')` after `vi.resetModules()`. This guarantees
 * the module sees the stubbed endpoint at the moment it captures it.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { InventoryProduct } from './inventoryService';

// Mock the signed fetch module: the service imports { signedFetch } from './signedFetch'.
vi.mock('./signedFetch', () => ({ signedFetch: vi.fn() }));

const API_ENDPOINT = 'https://manage.example.com/prod';

/**
 * Loads a fresh instance of the service module AND its mocked signedFetch, so that
 * the module captures the currently-stubbed VITE_MANAGE_API_ENDPOINT at load time.
 */
async function loadService() {
  const service = await import('./manageProductService');
  const { signedFetch } = await import('./signedFetch');
  return { service, signedFetch: signedFetch as ReturnType<typeof vi.fn> };
}

/**
 * Builds a minimal Response-like object. The service only touches `.ok`, `.status`
 * and `.json()`, so this framework-agnostic fake is the safest fixture.
 */
function fakeResponse(body: unknown, ok: boolean, status: number): Response {
  return {
    ok,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** A Response-like whose json() rejects, to exercise the `.catch(() => ({}))` path. */
function fakeResponseWithBadJson(ok: boolean, status: number): Response {
  return {
    ok,
    status,
    json: () => Promise.reject(new Error('invalid json')),
  } as unknown as Response;
}

/** An error that looks like a fetch abort (AbortController.abort()). */
function abortError(): Error {
  const err = new Error('The operation was aborted');
  err.name = 'AbortError';
  return err;
}

const fullProduct: InventoryProduct = {
  productId: 'p-123',
  productName: 'Milk',
  brand: 'Alpura',
  presentation: '1L carton',
  expirationDate: '2026-08-01',
  imageKey: 'users/u1/p-123.jpg',
  imageUrl: 'https://signed.example.com/p-123.jpg',
  createdAt: '2026-07-01T10:00:00.000Z',
  quantity: 2,
  unit: 'pack',
};

const updateFields = {
  productName: 'Milk',
  brand: 'Alpura',
  presentation: '1L carton',
  expirationDate: '2026-08-01',
};

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  vi.stubEnv('VITE_MANAGE_API_ENDPOINT', API_ENDPOINT);
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('updateProduct', () => {
  it('returns the parsed InventoryProduct and calls signedFetch with the correct request on success', async () => {
    const { service, signedFetch } = await loadService();
    signedFetch.mockResolvedValueOnce(fakeResponse(fullProduct, true, 200));

    const result = await service.updateProduct('p-123', updateFields);

    expect(result).toEqual(fullProduct);
    expect(signedFetch).toHaveBeenCalledTimes(1);

    const [calledUrl, calledOptions] = signedFetch.mock.calls[0];
    expect(calledUrl).toBe(`${API_ENDPOINT}/update-product`);
    expect(calledOptions.method).toBe('POST');
    expect(calledOptions.headers).toMatchObject({ 'Content-Type': 'application/json' });
    expect(calledOptions.body).toBe(JSON.stringify({ productId: 'p-123', ...updateFields }));
  });

  it('rejects with ManageProductError (NOT_FOUND) when the backend returns 404', async () => {
    const { service, signedFetch } = await loadService();
    signedFetch.mockResolvedValueOnce(
      fakeResponse({ error: 'NOT_FOUND', message: 'Product does not exist' }, false, 404),
    );

    await expect(service.updateProduct('p-999', updateFields)).rejects.toMatchObject({
      name: 'ManageProductError',
      code: 'NOT_FOUND',
      message: 'Product does not exist',
    });
  });

  it('rejects with ManageProductError (INVALID_PARAMS) when the backend returns 400', async () => {
    const { service, signedFetch } = await loadService();
    signedFetch.mockResolvedValueOnce(
      fakeResponse({ error: 'INVALID_PARAMS', message: 'Bad brand' }, false, 400),
    );

    await expect(service.updateProduct('p-123', updateFields)).rejects.toMatchObject({
      code: 'INVALID_PARAMS',
      message: 'Bad brand',
    });
  });

  it('rejects with ManageProductError (UNKNOWN) when the error body cannot be parsed', async () => {
    const { service, signedFetch } = await loadService();
    signedFetch.mockResolvedValueOnce(fakeResponseWithBadJson(false, 500));

    await expect(service.updateProduct('p-123', updateFields)).rejects.toMatchObject({
      code: 'UNKNOWN',
      message: 'Update failed (HTTP 500)',
    });
  });

  it('rejects with ManageProductError (TIMEOUT) when the request is aborted', async () => {
    const { service, signedFetch } = await loadService();
    signedFetch.mockRejectedValueOnce(abortError());

    await expect(service.updateProduct('p-123', updateFields)).rejects.toMatchObject({
      name: 'ManageProductError',
      code: 'TIMEOUT',
    });
  });
});

describe('deleteProduct', () => {
  it('returns { productId } and calls signedFetch with the correct request on success', async () => {
    const { service, signedFetch } = await loadService();
    signedFetch.mockResolvedValueOnce(fakeResponse({ productId: 'p-123' }, true, 200));

    const result = await service.deleteProduct('p-123');

    expect(result).toEqual({ productId: 'p-123' });
    expect(signedFetch).toHaveBeenCalledTimes(1);

    const [calledUrl, calledOptions] = signedFetch.mock.calls[0];
    expect(calledUrl).toBe(`${API_ENDPOINT}/delete-product`);
    expect(calledOptions.method).toBe('POST');
    expect(calledOptions.headers).toMatchObject({ 'Content-Type': 'application/json' });
    expect(calledOptions.body).toBe(JSON.stringify({ productId: 'p-123' }));
  });

  it('rejects with the mapped ManageProductError code on a non-2xx response', async () => {
    const { service, signedFetch } = await loadService();
    signedFetch.mockResolvedValueOnce(
      fakeResponse({ error: 'NOT_FOUND', message: 'Already deleted' }, false, 404),
    );

    await expect(service.deleteProduct('p-999')).rejects.toMatchObject({
      name: 'ManageProductError',
      code: 'NOT_FOUND',
      message: 'Already deleted',
    });
  });

  it('rejects with ManageProductError (TIMEOUT) when the request is aborted', async () => {
    const { service, signedFetch } = await loadService();
    signedFetch.mockRejectedValueOnce(abortError());

    await expect(service.deleteProduct('p-123')).rejects.toMatchObject({
      name: 'ManageProductError',
      code: 'TIMEOUT',
    });
  });
});

describe('missing env var', () => {
  it('throws a configuration Error when VITE_MANAGE_API_ENDPOINT is unset', async () => {
    // Override the beforeEach stub so the module captures an empty endpoint at load.
    vi.resetModules();
    vi.stubEnv('VITE_MANAGE_API_ENDPOINT', '');
    const { service } = await loadService();

    await expect(service.updateProduct('p-123', updateFields)).rejects.toThrow(
      /VITE_MANAGE_API_ENDPOINT/,
    );
  });
});
