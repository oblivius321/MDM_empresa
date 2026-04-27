import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Settings from './Settings';

const apiMocks = vi.hoisted(() => ({
  getMe: vi.fn(),
  updatePreferences: vi.fn(),
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'admin@example.com', is_admin: true },
  }),
}));

vi.mock('@/services/api', () => ({
  API_DISPLAY_URL: 'http://localhost:8200/api',
  buildApiUrl: (path: string) => `/api${path}`,
  userService: {
    getMe: apiMocks.getMe,
    updatePreferences: apiMocks.updatePreferences,
  },
}));

describe('Settings', () => {
  beforeEach(() => {
    apiMocks.getMe.mockReset();
    apiMocks.updatePreferences.mockReset();

    apiMocks.getMe.mockResolvedValue({
      data: {
        id: 1,
        email: 'admin@example.com',
        is_admin: true,
        is_active: true,
        created_at: '2026-04-13T12:00:00Z',
        preferences: {
          offline_alerts: false,
          compliance_failures: true,
          new_devices: true,
          system_updates: true,
        },
      },
    });

    apiMocks.updatePreferences.mockResolvedValue({
      data: {
        id: 1,
        email: 'admin@example.com',
        is_admin: true,
        is_active: true,
        created_at: '2026-04-13T12:00:00Z',
        preferences: {
          offline_alerts: true,
          compliance_failures: true,
          new_devices: true,
          system_updates: true,
        },
      },
    });
  });

  it('loads and persists notification preferences', async () => {
    render(<Settings />);

    const offlineToggle = await screen.findByRole('button', {
      name: 'Alertas de dispositivo offline',
    });

    expect(offlineToggle).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(offlineToggle);

    await waitFor(() => {
      expect(apiMocks.updatePreferences).toHaveBeenCalledWith({ offline_alerts: true });
    });
    expect(offlineToggle).toHaveAttribute('aria-pressed', 'true');
  });
});
