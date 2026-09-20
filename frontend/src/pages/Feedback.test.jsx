import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios from 'axios'
import Feedback from './Feedback'

vi.mock('axios', () => ({
  default: {
    post: vi.fn(),
  },
}))

describe('Feedback', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    localStorage.clear()

    localStorage.setItem(
      'user',
      JSON.stringify({
        user_id: 'user-001',
      }),
    )
  })

  it('renders the feedback form', () => {
    render(<Feedback />)

    expect(
      screen.getByRole('heading', {
        name: 'Feedback',
      }),
    ).toBeInTheDocument()

    expect(
      screen.getByText('Diagnosis Feedback'),
    ).toBeInTheDocument()

    expect(
      screen.getByLabelText('Comments'),
    ).toBeInTheDocument()
  })

  it('shows the output ID from the URL', () => {
    window.history.pushState(
      {},
      '',
      '/feedback?outputId=output-123',
    )

    render(<Feedback />)

    expect(
      screen.getByDisplayValue('output-123'),
    ).toBeInTheDocument()
  })

  it('submits feedback successfully', async () => {
    const user = userEvent.setup()

    axios.post.mockResolvedValue({
      data: {
        message: 'Feedback submitted successfully.',
      },
    })

    window.history.pushState(
      {},
      '',
      '/feedback?outputId=output-123',
    )

    render(<Feedback />)

    await user.click(
      screen.getByRole('radio', { name: 'Correct' }),
    )

    await user.click(
      screen.getByRole('button', {
        name: /submit feedback/i,
      }),
    )

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        'http://localhost:8000/api/feedback/',
        expect.objectContaining({
          user_id: 'user-001',
          output_id: 'output-123',
          is_correct: true,
        }),
        {
          withCredentials: true,
        },
      )
    })

    expect(
      await screen.findByText(
        'Feedback submitted successfully.',
      ),
    ).toBeInTheDocument()
  })

  it('shows an error when feedback submission fails', async () => {
    const user = userEvent.setup()

    axios.post.mockRejectedValue({
      response: {
        status: 500,
        data: {
          detail: 'Unable to submit feedback.',
        },
      },
    })

    window.history.pushState(
      {},
      '',
      '/feedback?outputId=output-123',
    )

    render(<Feedback />)

    await user.click(
      screen.getByRole('radio', { name: 'Correct' }),
    )

    await user.click(
      screen.getByRole('button', {
        name: /submit feedback/i,
      }),
    )

    expect(
      await screen.findByText(
        'Unable to submit feedback.',
      ),
    ).toBeInTheDocument()
  })
})
