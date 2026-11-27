import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import App from './App';

vi.mock('../api', () => ({
  hasAuthToken: () => true,
  setAuthToken: vi.fn(),
  getStatus: async () => ({ connected: true, status: 'enabled', audit: { valid: true, count: 4 }, sandbox: 'unavailable' }),
  getAgents: async () => [
    { name: 'master', role: 'master', implemented: true, status: 'available_not_running', capabilities: ['plan', 'propose'] },
    { name: 'developer', role: 'developer', implemented: true, status: 'available_not_running', capabilities: ['propose', 'sandbox'] },
  ],
  getLogs: async () => [],
  getTasks: async () => [],
  getMemory: async () => [],
}));

describe('CRI dashboard', () => {
  it('renders the responsive command center without fabricated telemetry', async () => {
    render(<App />);
    expect(await screen.findByText('CRI Command Center')).toBeTruthy();
    expect(screen.getByText('Available agents')).toBeTruthy();
    expect(screen.getByText('No proposals have been created yet.')).toBeTruthy();
  });

  it('navigates to the security posture page', async () => {
    render(<App />);
    fireEvent.click(await within(screen.getAllByRole('navigation', { name: 'Main navigation' })[0]).getByRole('button', { name: 'Security' }));
    expect(screen.getByText('Overnight Lockdown')).toBeTruthy();
    expect(screen.getByText(/Host-level watchdog template included; host installation and verification are still required./)).toBeTruthy();
  });
});
