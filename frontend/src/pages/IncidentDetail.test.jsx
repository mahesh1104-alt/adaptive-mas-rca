import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, act} from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import axios from 'axios'
import IncidentDetail from './IncidentDetail'

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

class MockWebSocket {
  static instances = []

  constructor() {
    this.onmessage = null
    this.onerror = null
    this.onclose = null
    MockWebSocket.instances.push(this)
  }

  close() {}

  send() {}
}

globalThis.WebSocket = MockWebSocket

const mockIncident = {
  incident_id: 'incident-001',
  report: {
    root_cause: 'Database connection failure',
    confidence: 0.85,
    supporting_evidence: [
      'Database connection errors detected',
    ],
  },
  agent_outputs: {
    log_analysis_agent: {
      confidence: 0.9,
      summary: 'Database connection errors found.',
    },
    metrics_analysis_agent: {
      confidence: 0.8,
      findings: [
        {
          metric: 'cpu_usage',
          value: 96,
          timestamp: '2026-09-20T10:05:00',
          service: 'order-service',
          observation: 'High CPU usage',
          relevance: 'Strongly related',
        },
      ],
    },
  },
  agent_output_ids: {
    reasoning_agent: 'output-001',
  },
}

const renderIncidentDetail = () =>
  render(
    <MemoryRouter initialEntries={['/incidents/incident-001']}>
      <Routes>
        <Route
          path="/incidents/:incidentId"
          element={<IncidentDetail />}
        />
      </Routes>
    </MemoryRouter>,
  )

describe('IncidentDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    MockWebSocket.instances = []
  })

  it('shows the loading state while the incident is fetched', () => {
    axios.get.mockReturnValue(new Promise(() => {}))

    renderIncidentDetail()

    expect(
      screen.getByText('Loading incident details...'),
    ).toBeInTheDocument()
  })

  it('renders the RCA report returned by the API', async () => {
    axios.get.mockResolvedValue({
      data: mockIncident,
    })

    renderIncidentDetail()

    expect(
      await screen.findByText('Database connection failure'),
    ).toBeInTheDocument()

    expect(screen.getByText('85.0%')).toBeInTheDocument()
    expect(screen.getByText('Agent Contribution Weights')).toBeInTheDocument()
    expect(screen.getByText('Metric Anomalies')).toBeInTheDocument()
  })

  it('shows an empty RCA state when no report exists', async () => {
    axios.get.mockResolvedValue({
      data: {
        incident_id: 'incident-001',
        report: null,
        agent_outputs: {},
      },
    })

    renderIncidentDetail()

    expect(
      await screen.findByRole('heading', {
        name: 'No RCA report yet',
      }),
    ).toBeInTheDocument()
  })

  it('starts a diagnosis job when Run Diagnosis is clicked', async () => {
    axios.get.mockResolvedValue({
      data: {
        incident_id: 'incident-001',
        report: null,
        agent_outputs: {},
      },
    })

    axios.post.mockResolvedValue({
      data: {
        job_id: 'job-001',
      },
    })

    renderIncidentDetail()

    const button = await screen.findByRole('button', {
      name: 'Run Diagnosis',
    })

    await act(async () => {
      await button.click()
    })

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        'http://localhost:8000/api/diagnosis',
        {
          incident_id: 'incident-001',
        },
        {
          withCredentials: true,
        },
      )
    })
  })
})
