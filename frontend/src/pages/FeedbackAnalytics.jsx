import { useEffect, useState } from 'react'
import axios from 'axios'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const API_BASE_URL = 'http://localhost:8000'

function FeedbackAnalytics() {
  const [period, setPeriod] = useState('daily')
  const [accuracyData, setAccuracyData] = useState([])
  const [mttrData, setMttrData] = useState([])
  const [loading, setLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    let cancelled = false

    const loadAnalytics = async () => {
      setLoading(true)
      setErrorMessage('')

      try {
        const [accuracyResponse, mttrResponse] =
          await Promise.all([
            axios.get(
              `${API_BASE_URL}/api/feedback/analytics/accuracy`,
              {
                params: { period },
                withCredentials: true,
              },
            ),
            axios.get(
              `${API_BASE_URL}/api/feedback/analytics/mttr`,
              {
                params: { period },
                withCredentials: true,
              },
            ),
          ])

        if (cancelled) {
          return
        }

        setAccuracyData(
          accuracyResponse.data?.data || [],
        )

        setMttrData(
          mttrResponse.data?.data || [],
        )
      } catch (requestError) {
        if (cancelled) {
          return
        }

        if (requestError.response?.status === 401) {
          setErrorMessage(
            'Your session has expired. Please login again.',
          )
        } else {
          setErrorMessage(
            requestError.response?.data?.detail ||
              'Unable to load feedback analytics.',
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadAnalytics()

    return () => {
      cancelled = true
    }
  }, [period])

  const totalFeedback = accuracyData.reduce(
    (total, item) => total + item.total_feedback,
    0,
  )

  const correctFeedback = accuracyData.reduce(
    (total, item) => total + item.correct_feedback,
    0,
  )

  const incorrectFeedback = accuracyData.reduce(
    (total, item) => total + item.incorrect_feedback,
    0,
  )

  const overallAccuracy =
    totalFeedback > 0
      ? correctFeedback / totalFeedback
      : 0

  const totalResolved = mttrData.reduce(
    (total, item) => total + item.resolved_incidents,
    0,
  )

  const averageMttr =
    totalResolved > 0
      ? mttrData.reduce(
          (total, item) =>
            total +
            item.mttr_minutes * item.resolved_incidents,
          0,
        ) / totalResolved
      : 0

  return (
    <section>
      <div className="page-heading">
        <div>
          <h2>Feedback Analytics</h2>
          <p>
            Monitor diagnosis feedback accuracy and incident
            resolution performance.
          </p>
        </div>

        <div className="analytics-period-control">
          <label htmlFor="analytics-period">
            Period
          </label>

          <select
            id="analytics-period"
            value={period}
            onChange={(event) =>
              setPeriod(event.target.value)
            }
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </div>
      </div>

      {loading && (
        <div className="page-loading">
          Loading feedback analytics...
        </div>
      )}

      {!loading && errorMessage && (
        <div className="error-state">
          <strong>Analytics unavailable</strong>
          <span>{errorMessage}</span>
        </div>
      )}

      {!loading && !errorMessage && (
        <>
          <div className="analytics-summary-grid">
            <div className="content-card analytics-summary-card">
              <span>Total Feedback</span>
              <strong>{totalFeedback}</strong>
            </div>

            <div className="content-card analytics-summary-card">
              <span>Feedback Accuracy</span>
              <strong>
                {(overallAccuracy * 100).toFixed(2)}%
              </strong>
            </div>

            <div className="content-card analytics-summary-card">
              <span>Correct Feedback</span>
              <strong>{correctFeedback}</strong>
            </div>

            <div className="content-card analytics-summary-card">
              <span>Average MTTR</span>
              <strong>
                {averageMttr.toFixed(2)} min
              </strong>
            </div>
          </div>

          <div className="content-card analytics-chart-card">
            <div className="analytics-card-heading">
              <div>
                <h3>Feedback Accuracy</h3>
                <p>
                  Correct and incorrect diagnosis feedback over time.
                </p>
              </div>
            </div>

            {accuracyData.length === 0 ? (
              <div className="empty-state">
                <h3>No feedback data</h3>
                <p>
                  There is no feedback available for the selected
                  period.
                </p>
              </div>
            ) : (
              <div className="responsive-chart analytics-chart">
                <ResponsiveContainer
                  width="100%"
                  height={320}
                  minWidth={280}
                >
                  <LineChart data={accuracyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis
                      domain={[0, 1]}
                      tickFormatter={(value) =>
                        `${Math.round(value * 100)}%`
                      }
                    />
                    <Tooltip
                      formatter={(value) =>
                        `${(Number(value) * 100).toFixed(2)}%`
                      }
                    />
                    <Line
                      type="monotone"
                      dataKey="accuracy"
                      name="Accuracy"
                      strokeWidth={2}
                      dot
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className="content-card analytics-chart-card">
            <div className="analytics-card-heading">
              <div>
                <h3>MTTR Trend</h3>
                <p>
                  Average mean time to resolution for resolved
                  incidents.
                </p>
              </div>
            </div>

            {mttrData.length === 0 ? (
              <div className="empty-state">
                <h3>No MTTR data</h3>
                <p>
                  There are no resolved incidents for the selected
                  period.
                </p>
              </div>
            ) : (
              <div className="responsive-chart analytics-chart">
                <ResponsiveContainer
                  width="100%"
                  height={320}
                  minWidth={280}
                >
                  <LineChart data={mttrData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis />
                    <Tooltip
                      formatter={(value) =>
                        `${Number(value).toFixed(2)} min`
                      }
                    />
                    <Line
                      type="monotone"
                      dataKey="mttr_minutes"
                      name="MTTR"
                      strokeWidth={2}
                      dot
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className="content-card analytics-breakdown-card">
            <h3>Feedback Breakdown</h3>

            <div className="analytics-breakdown-grid">
              <div>
                <span>Correct</span>
                <strong>{correctFeedback}</strong>
              </div>

              <div>
                <span>Incorrect</span>
                <strong>{incorrectFeedback}</strong>
              </div>

              <div>
                <span>Resolved Incidents</span>
                <strong>{totalResolved}</strong>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  )
}

export default FeedbackAnalytics
