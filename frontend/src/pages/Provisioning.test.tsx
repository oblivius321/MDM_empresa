import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Provisioning from './Provisioning';

const apiMocks = vi.hoisted(() => ({
  listProfiles: vi.fn(),
  getPolicies: vi.fn(),
  androidStatus: vi.fn(),
  createEnrollmentToken: vi.fn(),
}));

vi.mock('@/services/api', () => ({
  enrollmentService: {
    listProfiles: apiMocks.listProfiles,
    createProfile: vi.fn(),
    updateProfile: vi.fn(),
    previewProfile: vi.fn(),
  },
  policyV2Service: {
    getAll: apiMocks.getPolicies,
  },
  androidManagementService: {
    status: apiMocks.androidStatus,
    createSignupUrl: vi.fn(),
    upsertDefaultPolicy: vi.fn(),
    createEnrollmentToken: apiMocks.createEnrollmentToken,
  },
}));

describe('Provisioning', () => {
  beforeEach(() => {
    apiMocks.listProfiles.mockReset();
    apiMocks.getPolicies.mockReset();
    apiMocks.androidStatus.mockReset();
    apiMocks.createEnrollmentToken.mockReset();
    Object.defineProperty(window, 'scrollTo', { value: vi.fn(), writable: true });

    apiMocks.listProfiles.mockResolvedValue({
      data: [
        {
          id: 'profile-1',
          name: 'Coletores Galpao A',
          kiosk_enabled: true,
          allowed_apps: [],
          blocked_features: {},
          config: {},
          policy_ids: [10],
          version: 3,
          is_active: true,
          created_at: '2026-04-13T10:00:00Z',
        },
      ],
    });
    apiMocks.getPolicies.mockResolvedValue({ data: [] });
    apiMocks.androidStatus.mockResolvedValue({
      data: {
        configured: true,
        project_id: 'mdm-projeto2',
        enterprise_name: 'enterprises/LC017i75s8',
        service_account_email: 'elion-mdm-service@mdm-projeto2.iam.gserviceaccount.com',
      },
    });
    apiMocks.createEnrollmentToken.mockResolvedValue({
      status: 200,
      data: {
        id: 'token-id',
        name: 'enterprises/LC017i75s8/enrollmentTokens/token-123',
        qr_code: 'raw-google-qr-token-123',
        expiration: '2026-04-13T10:15:00Z',
        expiration_timestamp: '2026-04-13T10:15:00Z',
      },
    });
  });

  it('generates an official Android Management QR Code', async () => {
    render(<Provisioning />);

    expect(await screen.findByText('Coletores Galpao A')).toBeInTheDocument();

    const buttons = screen.getAllByRole('button', { name: /gerar qr oficial \(android enterprise\)/i });
    fireEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => {
      expect(apiMocks.createEnrollmentToken).toHaveBeenCalledWith({});
    });

    expect(await screen.findByTestId('android-management-qr-code')).toBeInTheDocument();
    expect(document.getElementById('android-management-qr-code')?.tagName.toLowerCase()).toBe('svg');
    expect(screen.getByText('Use este QR para provisionamento Android Enterprise via Google.')).toBeInTheDocument();
    expect(screen.getAllByText(/token-123/).length).toBeGreaterThan(0);
  });
});
