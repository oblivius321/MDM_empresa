import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Logs from './Logs';

const apiMocks = vi.hoisted(() => ({
  getAll: vi.fn(),
}));

vi.mock('@/services/api', () => ({
  logService: {
    getAll: apiMocks.getAll,
  },
}));

describe('Logs', () => {
  beforeEach(() => {
    apiMocks.getAll.mockReset();
    apiMocks.getAll.mockResolvedValue({
      data: [
        {
          id: 'audit-1',
          user_id: 1,
          user_email: 'admin@example.com',
          action: 'COMMAND_UPDATE',
          event_type: 'USER_PREFERENCES_UPDATE',
          severity: 'INFO',
          actor_type: 'admin',
          actor_id: 'admin@example.com',
          resource_type: 'system',
          resource_id: null,
          device_id: null,
          details: {
            message: 'Configuracoes de notificacao atualizadas',
          },
          is_success: true,
          error_message: null,
          created_at: '2026-04-13T12:00:00Z',
        },
      ],
    });
  });

  it('renders real audit logs from the API', async () => {
    render(<Logs />);

    expect(apiMocks.getAll).toHaveBeenCalledWith({ limit: 500 });
    expect(await screen.findByText('Configuracoes de notificacao atualizadas')).toBeInTheDocument();
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
    expect(screen.getByText('SUCCESS')).toBeInTheDocument();
  });
});
