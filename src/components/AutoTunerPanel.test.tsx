import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AutoTunerPanel from './AutoTunerPanel';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch as any;

const MOCK_STATUS = {
  active: true,
  total_cycles: 12,
  accepted_mutations: 8,
  rejected_mutations: 4,
  baseline_fitness: 0.65,
  current_fitness: 0.72,
  last_cycle_time: Date.now() / 1000,
  last_commit: 'abc123',
  gene_count: 15,
  genes: { temperature: 0.7, num_ctx: 4096 },
  fitness_history: [
    { cycle: 11, fitness_before: 0.68, fitness_after: 0.72, mutations: 3, accepted: true, elapsed_sec: 1.2 },
    { cycle: 10, fitness_before: 0.65, fitness_after: 0.68, mutations: 2, accepted: true, elapsed_sec: 0.9 },
  ],
};

const MOCK_GENES = {
  genes: [
    {
      name: 'temperature',
      value: 0.7,
      min_val: 0.1,
      max_val: 1.0,
      mutation_rate: 0.05,
      step_size: 0,
      description: 'LLM sampling temperature',
    },
    {
      name: 'num_ctx',
      value: 4096,
      min_val: 2048,
      max_val: 16384,
      mutation_rate: 0.1,
      step_size: 512,
      description: 'Ollama context window size',
    },
  ],
};

function mockApi(
  status: typeof MOCK_STATUS | null = MOCK_STATUS,
  genes: typeof MOCK_GENES = MOCK_GENES,
) {
  mockFetch.mockImplementation((url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    if (url.includes('/auto-tuner/genes') && method === 'GET') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(genes) });
    }
    if (url.includes('/auto-tuner') && method === 'POST' && url.includes('/evolve')) {
      return Promise.resolve({ ok: true });
    }
    if (url.includes('/auto-tuner/gene') && method === 'POST') {
      return Promise.resolve({ ok: true });
    }
    if (url.includes('/auto-tuner/reset') && method === 'POST') {
      return Promise.resolve({ ok: true });
    }
    if (url.includes('/auto-tuner/history/clear') && method === 'POST') {
      return Promise.resolve({ ok: true });
    }
    if (url.includes('/auto-tuner') && method === 'GET') {
      if (status === null) return Promise.resolve({ ok: false });
      return Promise.resolve({ ok: true, json: () => Promise.resolve(status) });
    }
    return Promise.resolve({ ok: false });
  });
}

describe('AutoTunerPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi();
  });

  it('renders the panel header', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    expect(screen.getByText('Auto-Tuner')).toBeDefined();
  });

  it('renders status bar with correct values', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('12')).toBeDefined(); // total_cycles
      expect(screen.getByText('8')).toBeDefined();  // accepted
      expect(screen.getByText('4')).toBeDefined();  // rejected
    });
  });

  it('displays fitness as percentage', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('72.0%')).toBeDefined(); // current_fitness
    });
  });

  it('renders gene cards', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('temperature')).toBeDefined();
      expect(screen.getByText('num_ctx')).toBeDefined();
      expect(screen.getByText('LLM sampling temperature')).toBeDefined();
      expect(screen.getByText('Ollama context window size')).toBeDefined();
    });
  });

  it('renders gene count header', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText(/Tunable Genes/)).toBeDefined();
    });
  });

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    await act(async () => {
      render(<AutoTunerPanel onClose={onClose} />);
    });
    fireEvent.click(screen.getByText('✕'));
    expect(onClose).toHaveBeenCalled();
  });

  it('enables evolve button and calls API', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    const evolveBtn = screen.getByText(/Run Evolution Cycle/);
    expect(evolveBtn).not.toBeNull();

    await act(async () => {
      fireEvent.click(evolveBtn);
    });

    // evolve should have been called
    const evolveCalls = mockFetch.mock.calls.filter(
      (c) => typeof c[0] === 'string' && c[0].includes('/evolve'),
    );
    expect(evolveCalls.length).toBeGreaterThanOrEqual(1);
  });

  it('enters edit mode when gene value is clicked', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('temperature')).toBeDefined();
    });

    // Click the gene value button to enter edit mode
    // The temperature value is displayed as "0.7000"
    const valueButtons = screen.getAllByText('0.7000');
    fireEvent.click(valueButtons[0]);

    // Should now show an input field
    const input = screen.getByRole('spinbutton');
    expect(input).not.toBeNull();
  });

  it('validates NaN input before calling setGene', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('temperature')).toBeDefined();
    });

    // Enter edit mode
    const valueButtons = screen.getAllByText('0.7000');
    fireEvent.click(valueButtons[0]);

    const input = screen.getByRole('spinbutton') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'not-a-number' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    // setGene should NOT have been called because input is NaN
    // Filter out /auto-tuner/genes (GET) — only look for /auto-tuner/gene (POST)
    const geneSetCalls = mockFetch.mock.calls.filter(
      (c) => typeof c[0] === 'string' && c[0].includes('/auto-tuner/gene') && !c[0].includes('/auto-tuner/genes'),
    );
    expect(geneSetCalls.length).toBe(0);
  });

  it('calls setGene with valid numeric input', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('temperature')).toBeDefined();
    });

    // Enter edit mode
    const valueButtons = screen.getAllByText('0.7000');
    fireEvent.click(valueButtons[0]);

    const input = screen.getByRole('spinbutton') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '0.85' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      // Filter out /auto-tuner/genes (GET) — only look for /auto-tuner/gene (POST)
      const geneSetCalls = mockFetch.mock.calls.filter(
        (c) => typeof c[0] === 'string' && c[0].includes('/auto-tuner/gene') && !c[0].includes('/auto-tuner/genes'),
      );
      expect(geneSetCalls.length).toBeGreaterThanOrEqual(1);
      const body = JSON.parse(geneSetCalls[0][1]?.body as string);
      expect(body).toMatchObject({ name: 'temperature', value: 0.85 });
    });
  });

  it('cancels edit mode on Escape key', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('temperature')).toBeDefined();
    });

    // Enter edit mode
    const valueButtons = screen.getAllByText('0.7000');
    fireEvent.click(valueButtons[0]);

    const input = screen.getByRole('spinbutton');
    fireEvent.keyDown(input, { key: 'Escape' });

    // Input should be gone
    await waitFor(() => {
      expect(screen.queryByRole('spinbutton')).toBeNull();
    });
  });

  it('shows fitness history chart when data exists', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    await waitFor(() => {
      expect(screen.getByText('Fitness History')).toBeDefined();
      expect(screen.getByText(/Last 2 cycles/)).toBeDefined();
    });
  });

  it('renders Reset and Clear buttons', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    expect(screen.getByText('Reset')).toBeDefined();
    expect(screen.getByText('Clear')).toBeDefined();
  });

  it('handles API failure gracefully', async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: false }),
    );

    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });

    // Should render without crashing — shows default zero values
    expect(screen.getByText('Auto-Tuner')).toBeDefined();
    expect(screen.getAllByText('0').length).toBeGreaterThan(0); // default cycles/accepted/rejected
  });

  it('handles network error gracefully', async () => {
    mockFetch.mockImplementation(() =>
      Promise.reject(new Error('Network error')),
    );

    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });

    // Should not crash
    expect(screen.getByText('Auto-Tuner')).toBeDefined();
  });

  it('displays integer gene values for step_size > 0', async () => {
    await act(async () => {
      render(<AutoTunerPanel onClose={vi.fn()} />);
    });
    await waitFor(() => {
      // num_ctx has step_size=512, so value 4096 should display as integer
      expect(screen.getByText('4096')).toBeDefined();
    });
  });
});
