import { useState } from 'react'
import axios from 'axios'

function Feedback() {
  const [outputId, setOutputId] = useState(
    () =>
      new URLSearchParams(window.location.search).get('outputId') || '',
  )
  const [isCorrect, setIsCorrect] = useState('')
  const [rating, setRating] = useState('')
  const [comments, setComments] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')
  const [errorMessage, setErrorMessage] = useState('')

  const submitFeedback = async (event) => {
    event.preventDefault()

    setSubmitting(true)
    setSuccessMessage('')
    setErrorMessage('')

    try {
      const user = JSON.parse(
        localStorage.getItem('user') || '{}',
      )

      if (!user.user_id) {
        setErrorMessage(
          'Your session has expired. Please log in again.',
        )
        return
      }

      const response = await axios.post(
        'http://localhost:8000/api/feedback/',
        {
          user_id: user.user_id,
          output_id: outputId,
          is_correct: isCorrect === 'true',
          rating: rating ? Number(rating) : null,
          comments: comments.trim() || null,
        },
        {
          withCredentials: true,
        },
      )

      setSuccessMessage(
        response.data.message ||
          'Feedback submitted successfully.',
      )

      setIsCorrect('')
      setRating('')
      setComments('')
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        setErrorMessage(
          'Your session has expired. Please log in again.',
        )
      } else {
        setErrorMessage(
          requestError.response?.data?.detail ||
            'Unable to submit feedback.',
        )
      }
    } finally {
      setSubmitting(false)
    }
  }

  const outputIdFromUrl =
    new URLSearchParams(window.location.search).get('outputId')

  return (
    <section>
      <div className="page-heading">
        <div>
          <h2>Feedback</h2>
          <p>Confirm or correct the reported root cause.</p>
        </div>
      </div>

      <div className="content-card feedback-card">
        <h3>Diagnosis Feedback</h3>

        <p>
          Tell us whether the reported diagnosis was correct and add
          any additional information that can help improve future RCA
          results.
        </p>

        <form
          className="feedback-form"
          onSubmit={submitFeedback}
        >
          <label htmlFor="output-id">
            Agent Output ID
          </label>

          <input
            id="output-id"
            type="text"
            value={outputId}
            onChange={(event) => setOutputId(event.target.value)}
            placeholder="Enter the agent output ID"
            readOnly={Boolean(outputIdFromUrl)}
            required
          />

          {outputId && (
            <span className="feedback-context">
              Selected from the diagnosis you are reviewing.
            </span>
          )}

          <label>
            Was the reported root cause correct?
          </label>

          <div className="feedback-choice-group">
            <label className="feedback-choice">
              <input
                type="radio"
                name="isCorrect"
                value="true"
                checked={isCorrect === 'true'}
                onChange={(event) =>
                  setIsCorrect(event.target.value)
                }
                required
              />

              Correct
            </label>

            <label className="feedback-choice">
              <input
                type="radio"
                name="isCorrect"
                value="false"
                checked={isCorrect === 'false'}
                onChange={(event) =>
                  setIsCorrect(event.target.value)
                }
              />

              Incorrect
            </label>
          </div>

          <label htmlFor="rating">Rating</label>

          <select
            id="rating"
            value={rating}
            onChange={(event) => setRating(event.target.value)}
          >
            <option value="">Select a rating</option>
            <option value="5">5 — Excellent</option>
            <option value="4">4 — Good</option>
            <option value="3">3 — Average</option>
            <option value="2">2 — Poor</option>
            <option value="1">1 — Very poor</option>
          </select>

          <label htmlFor="comments">Comments</label>

          <textarea
            id="comments"
            value={comments}
            onChange={(event) => setComments(event.target.value)}
            placeholder="Explain what was correct or what should be changed..."
            rows={6}
          />

          <button
            type="submit"
            disabled={submitting}
          >
            {submitting
              ? 'Submitting...'
              : 'Submit Feedback'}
          </button>
        </form>

        {successMessage && (
          <div className="feedback-success">
            {successMessage}
          </div>
        )}

        {errorMessage && (
          <div className="error-state">
            <strong>Feedback could not be submitted</strong>
            <span>{errorMessage}</span>
          </div>
        )}
      </div>
    </section>
  )
}

export default Feedback