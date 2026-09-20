import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import axios from 'axios'
import Incidents from './Incidents'

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
  },
}))

const renderIncidents = () =>
  render(
    <MemoryRouter>
      <Incidents />
    </MemoryRouter>,
  )

const mockIncidents = [
  {
    incident_id: 'incident-001',
    title: 'Order Service CPU Spike',
    status: 'open',
    source: 'order-service',
    severity: 'high',
    created_at: '2026-09-20T10:00:00Z',
  },
  {
    incident_id: 'incident-002',
    title: 'Payment Service Latency',
    status: 'resolved',
    source: 'payment-service',
    severity: 'medium',
    created_at: '2026-09-20T11:00:00Z',
  },
]

describe('Incidents', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the loading state while incidents are being fetched', () => {
    axios.get.mockReturnValue(new Promise(() => {}))

    renderIncidents()

    expect(
      screen.getByText('Loading incidents...'),
    ).toBeInTheDocument()
  })

  it('renders incidents returned by the API', async () => {
    axios.get.mockResolvedValue({
      data: mockIncidents,
    })

    renderIncidents()

    expect(
      await screen.findByText('Order Service CPU Spike'),
    ).toBeInTheDocument()

    expect(
      screen.getByText('Payment Service Latency'),
    ).toBeInTheDocument()

    expect(screen.getAllByText('order-service').length).toBeGreaterThan(0)
    expect(screen.getAllByText('payment-service').length).toBeGreaterThan(0)

    expect(axios.get).toHaveBeenCalledWith(
      'http://localhost:8000/api/incidents',
      {
        withCredentials: true,
      },
    )
  })

  it('shows the empty state when the API returns no incidents', async () => {
    axios.get.mockResolvedValue({
      data: [],
    })

    renderIncidents()

    expect(
      await screen.findByRole('heading', { name: 'No incidents found' }),
    ).toBeInTheDocument()
  })

  it('shows an error when the API request fails', async () => {
    axios.get.mockRejectedValue(new Error('Backend unavailable'))

    renderIncidents()

    expect(
      await screen.findByText(
        'Unable to load incidents from the backend.',
      ),
    ).toBeInTheDocument()
  })
})

