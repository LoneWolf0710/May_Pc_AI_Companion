import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import InternetLearning from './InternetLearning';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch as any;

const MOCK_STATUS = {
  total_extracted: 42,
  total_approved: 30,
  total_rejected: 5,
  total_pending: 7,
  pending_count: 7,
  learned_count: 30,
};

const MOCK_PENDING = {
  items: [
    {
      id: 'item-1',
      query: 'What is Rust programming language?',
      source: 'https://example.com/rust',
      facts: ['Rust is a systems language', 'Rust focuses on safety'],
      confidence: 0.85,
      timestamp: Date.now() / 1000,
      status: 'pending',
    },
    {
      id: 'item-2',
      query: 'Tauri vs Electron performance',
      source: 'https://example.com/tauri-electron',
      facts: ['Tauri uses system webview', 'Tauri has smaller bundle size'],
      confidence: 0.45,
      timestamp: Date.now() / 1000,
      status: 'pending',
    },
  ],
};

const MOCK_RECENT = {
  items: [
    {
      id: 'recent-1',
      query: 'React hooks best practices',
      source: 'https://example.com/hooks',
      facts: ['Use hooks for state', 'Avoid deep nesting'],
      confidence: 0.92,
      timestamp: Date.now() / 1000,
      status: 'approved',
    },
  ],
};

function mockApi(
  status: typeof MOCK_STATUS | null = MOCK_STATUS,
  pending: typeof MOCK_PENDING = MOCK_PENDING,
  recent: typeof MOCK_RECENT = MOCK_RECENT,
) {
  mockFetch.mockImplementation((url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    if (url.includes('/learning/pending') && method === 'GET') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(pending) });
    }
    if (url.includes('/learning/recent') && method === 'GET') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(recent) });
    }
    if (url.includes('/learning/approve') && method === 'POST') {
      return Promise.resolve({ ok: true });
    }
    if (url.includes('/learning/reject') && method === 'POST') {
      return Promise.resolve({ ok: true });
    }
    if (url.includes('/learning/clear') && method === 'POST') {
      return Promise.resolve({ ok: true });
    }
    if (url.includes('/learning') && method === 'GET') {
      if (status === null) return Promise.resolve({ ok: false });
      return Promise.resolve({ ok: true, json: () => Promise.resolve(status) });
    }
    return Promise.resolve({ ok: false });
  });
}

describe('InternetLearning', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi();
  });

  it('renders the panel header', async () => {
    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    expect(screen.getByText('Internet Learning')).toBeDefined();
  });

  it('renders status bar with correct values', async () => {
    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('7')).toBeDefined();   // pending_count
      expect(screen.getByText('30')).toBeDefined();  // learned_count
    });
  });

  it('renders pending knowledge cards', async () => {
    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('What is Rust programming language?')).toBeDefined();
      expect(screen.getByText('Tauri vs Electron performance')).toBeDefined();
    });
  });

  it('displays confidence percentage on cards', async () => {
    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('85% conf')).toBeDefined();
      expect(screen.getByText('45% conf')).toBeDefined();
    });
  });

  it('displays facts for pending items', async () => {
    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('Rust is a systems language')).toBeDefined();
      expect(screen.getByText('Rust focuses on safety')).toBeDefined();
    });
  });

  it('renders recently learned section', async () => {
    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText(/Recently Learned/)).toBeDefined();
      expect(screen.getByText(/React hooks best practices/)).toBeDefined();
    });
  });

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    await act(async () => {
      render(<InternetLearning onClose={onClose} />);
    });
    fireEvent.click(screen.getByText('✕'));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls approve API when Learn button is clicked', async () => {
    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('What is Rust programming language?')).toBeDefined();
    });

    const learnButtons = screen.getAllByText('✓ Learn');
    await act(async () => {
      fireEvent.click(learnButtons[0]);
    });

    await waitFor(() => {
      const approveCalls = mockFetch.mock.calls.filter(
        (c) => typeof c[0] === 'string' && c[0].includes('/learning/approve'),
      );
      expect(approveCalls.length).toBeGreaterThanOrEqual(1);
      const body = JSON.parse(approveCalls[0][1]?.body as string);
      expect(body).toEqual({ id: 'item-1' });
    });
  });

  it('calls reject API when Discard button is clicked', async () => {
    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('Tauri vs Electron performance')).toBeDefined();
    });

    const discardButtons = screen.getAllByText('✕ Discard');
    await act(async () => {
      fireEvent.click(discardButtons[0]);
    });

    await waitFor(() => {
      const rejectCalls = mockFetch.mock.calls.filter(
        (c) => typeof c[0] === 'string' && c[0].includes('/learning/reject'),
      );
      expect(rejectCalls.length).toBeGreaterThanOrEqual(1);
      const body = JSON.parse(rejectCalls[0][1]?.body as string);
      expect(body).toEqual({ id: 'item-1' });
    });
  });

  it('calls clear API when Clear All Pending is clicked', async () => {
    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('Clear All Pending')).toBeDefined();
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Clear All Pending'));
    });

    await waitFor(() => {
      const clearCalls = mockFetch.mock.calls.filter(
        (c) => typeof c[0] === 'string' && c[0].includes('/learning/clear'),
      );
      expect(clearCalls.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows empty state when no pending items', async () => {
    mockApi(MOCK_STATUS, { items: [] }, MOCK_RECENT);

    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText(/No pending knowledge items/)).toBeDefined();
    });
  });

  it('hides Clear All button when no pending items', async () => {
    mockApi(MOCK_STATUS, { items: [] }, MOCK_RECENT);

    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.queryByText('Clear All Pending')).toBeNull();
    });
  });

  it('truncates long source URLs', async () => {
    const longUrl = 'https://example.com/' + 'a'.repeat(100);
    mockApi(MOCK_STATUS, {
      items: [{
        id: 'item-long',
        query: 'Long URL test',
        source: longUrl,
        facts: [],
        confidence: 0.8,
        timestamp: Date.now() / 1000,
        status: 'pending',
      }],
    }, { items: [] });

    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });

    // Source should be truncated — check that it ends with '...'
    await waitFor(() => {
      const sourceEl = screen.getByText(/\.\.\.$/);
      expect(sourceEl).toBeDefined();
    });
  });

  it('limits displayed facts to 3 per item', async () => {
    const manyFactsItem = {
      id: 'item-many',
      query: 'Many facts',
      source: 'https://example.com/many',
      facts: ['fact1', 'fact2', 'fact3', 'fact4', 'fact5'],
      confidence: 0.9,
      timestamp: Date.now() / 1000,
      status: 'pending',
    };
    mockApi(MOCK_STATUS, { items: [manyFactsItem] }, { items: [] });

    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('fact1')).toBeDefined();
      expect(screen.getByText('fact2')).toBeDefined();
      expect(screen.getByText('fact3')).toBeDefined();
      expect(screen.queryByText('fact4')).toBeNull();
    });
  });

  it('handles API failure gracefully', async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: false }),
    );

    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });

    // Should render without crashing
    expect(screen.getByText('Internet Learning')).toBeDefined();
  });

  it('handles network error gracefully', async () => {
    mockFetch.mockImplementation(() =>
      Promise.reject(new Error('Network error')),
    );

    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });

    // Should not crash
    expect(screen.getByText('Internet Learning')).toBeDefined();
  });

  it('disables buttons while loading', async () => {
    // Mock a slow approve response — use a deferred promise for approve
    const deferred: { resolve: (() => void) | null } = { resolve: null };
    mockFetch.mockImplementation((url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET';
      if (url.includes('/learning/approve') && method === 'POST') {
        return new Promise((resolve) => {
          deferred.resolve = () => resolve({ ok: true });
        });
      }
      // All other endpoints return immediately with proper mock data
      if (url.includes('/learning/pending') && method === 'GET') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_PENDING) });
      }
      if (url.includes('/learning/recent') && method === 'GET') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_RECENT) });
      }
      if (url.includes('/learning') && method === 'GET') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_STATUS) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_STATUS) });
    });

    await act(async () => {
      render(<InternetLearning onClose={vi.fn()} />);
    });

    // Wait for pending items to render
    await waitFor(() => {
      const buttons = screen.getAllByRole('button');
      const learnBtn = buttons.find((b) => b.textContent?.includes('Learn'));
      expect(learnBtn).toBeDefined();
    });

    // Click approve — buttons should be disabled during loading
    const learnButtons = screen.getAllByRole('button').filter((b) =>
      b.textContent?.includes('Learn'),
    );
    await act(async () => {
      fireEvent.click(learnButtons[0]);
    });

    // All Learn/Discard buttons should be disabled
    const allButtons = screen.getAllByRole('button');
    const actionButtons = allButtons.filter((btn) =>
      btn.textContent?.includes('Learn') || btn.textContent?.includes('Discard'),
    );
    expect(actionButtons.length).toBeGreaterThanOrEqual(2);
    actionButtons.forEach((btn) => {
      expect(btn).toBeDisabled();
    });

    // Resolve the pending request
    deferred.resolve?.();
  });
});
