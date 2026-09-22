import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import FeedbackAnalytics from './FeedbackAnalytics'

vi.mock('axios')

describe('FeedbackAnalytics', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    axios.get.mockImplementation((url) => {
      if (url.includes('/accuracy')) {
        return Promise.resolve({
          data: {
            period: 'daily',
            data: [
              {
                period: '2026-09-18',
                total_feedback: 4,
                correct_feedback: 3,
                incorrect_feedback: 1,
                accuracy: 0.75,
              },
              {
                period: '2026-09-20',
                total_feedback: 2,
                correct_feedback: 0,
                incorrect_feedback: 2,
                accuracy: 0,
              },
              {
                period: '2026-09-22',
                total_feedback: 3,
                correct_feedback: 2,
                incorrect_feedback: 1,
                accuracy: 0.6667,
              },
            ],
          },
        })
      }

      return Promise.resolve({
        data: {
          period: 'daily',
          data: [
            {
              period: '2026-09-18',
              resolved_incidents: 1,
              mttr_seconds: 3600,
              mttr_minutes: 60,
            },
            {
              period: '2026-09-19',
              resolved_incidents: 2,
              mttr_seconds: 7200,
              mttr_minutes: 60,
            },
          ],
        },
      })
    })
  })

  it('loads and displays feedback analytics', async () => {
    render(
      <MemoryRouter>
        <FeedbackAnalytics />
      </MemoryRouter>,
    )

    expect(
      screen.getByText('Loading feedback analytics...'),
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Feedback Analytics')).toBeInTheDocument()
    })

    expect(screen.getByText('Total Feedback')).toBeInTheDocument()
    expect(screen.getByText('9')).toBeInTheDocument()
    expect(screen.getByText('55.56%')).toBeInTheDocument()
    expect(screen.getByText('Correct Feedback')).toBeInTheDocument()
    expect(screen.getAllByText('5')).toHaveLength(2)
    expect(screen.getByText('Average MTTR')).toBeInTheDocument()
    expect(screen.getByText('60.00 min')).toBeInTheDocument()
  })

  it('requests the selected daily period with credentials', async () => {
    render(
      <MemoryRouter>
        <FeedbackAnalytics />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledTimes(2)
    })

    expect(axios.get).toHaveBeenCalledWith(
      'http://localhost:8000/api/feedback/analytics/accuracy',
      {
        params: { period: 'daily' },
        withCredentials: true,
      },
    )

    expect(axios.get).toHaveBeenCalledWith(
      'http://localhost:8000/api/feedback/analytics/mttr',
      {
        params: { period: 'daily' },
        withCredentials: true,
      },
    )
  })

  it('displays an error when analytics requests fail', async () => {
    axios.get.mockRejectedValueOnce({
      response: {
        status: 500,
        data: {
          detail: 'Analytics service unavailable',
        },
      },
    })

    axios.get.mockResolvedValueOnce({
      data: {
        period: 'daily',
        data: [],
      },
    })

    render(
      <MemoryRouter>
        <FeedbackAnalytics />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getByText('Analytics service unavailable'),
      ).toBeInTheDocument()
    })

    expect(screen.getByText('Analytics unavailable')).toBeInTheDocument()
  })
})
