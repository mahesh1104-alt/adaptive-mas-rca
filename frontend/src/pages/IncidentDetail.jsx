import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import axios from 'axios'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const AGENTS = [
  {
    key: 'log_analysis_agent',
    label: 'Log Analysis Agent',
  },
  {
    key: 'metrics_analysis_agent',
    label: 'Metrics Analysis Agent',
  },
  {
    key: 'source_code_analysis_agent',
    label: 'Source Code Analysis Agent',
  },
  {
    key: 'trace_analysis_agent',
    label: 'Trace Analysis Agent',
  },
  {
    key: 'knowledge_retrieval_agent',
    label: 'Knowledge Retrieval Agent',
  },
  {
    key: 'reasoning_agent',
    label: 'Reasoning Agent',
  },
  {
    key: 'validation_agent',
    label: 'Validation Agent',
  },
]

const createInitialProgress = () =>
  Object.fromEntries(
    AGENTS.map((agent) => [
      agent.key,
      {
        status: 'pending',
        confidence: null,
        summary: '',
      },
    ]),
  )

function IncidentDetail() {
  const { incidentId } = useParams()

  const [incident, setIncident] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [diagnosisStarting, setDiagnosisStarting] = useState(false)
  const [diagnosisRunning, setDiagnosisRunning] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [diagnosisError, setDiagnosisError] = useState('')
  const [progress, setProgress] = useState(createInitialProgress)

  useEffect(() => {
    const fetchIncident = async () => {
      setLoading(true)
      setError('')

      try {
        const response = await axios.get(
          `http://localhost:8000/api/diagnosis/incidents/${incidentId}`,
          {
            withCredentials: true,
          },
        )

        setIncident(response.data)
      } catch (requestError) {
        if (requestError.response?.status === 401) {
          setError('Your session has expired. Please log in again.')
        } else if (requestError.response?.status === 404) {
          setError('Incident not found.')
        } else {
          setError('Unable to load incident details.')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchIncident()
  }, [incidentId])

  useEffect(() => {
    if (!jobId) {
      return undefined
    }

    // The browser automatically sends the HttpOnly access_token
    // cookie during the WebSocket handshake.
    const socket = new WebSocket(
      `ws://localhost:8000/api/diagnosis/ws/${jobId}`,
    )

    socket.onmessage = (messageEvent) => {
      try {
        const event = JSON.parse(messageEvent.data)

        if (event.event === 'diagnosis_started') {
          setDiagnosisRunning(true)

          setProgress((current) => {
            const next = Object.fromEntries(
              AGENTS.map((agent) => [
                agent.key,
                {
                  ...current[agent.key],
                  status:
                    current[agent.key].status === 'done'
                      ? 'done'
                      : 'pending',
                },
              ]),
            )

            const firstPendingAgent = AGENTS.find(
              (agent) => next[agent.key].status === 'pending',
            )

            if (firstPendingAgent) {
              next[firstPendingAgent.key] = {
                ...next[firstPendingAgent.key],
                status: 'running',
              }
            }

            return next
          })
        }

        if (event.event === 'agent_completed') {
          const completedAgent = event.agent

          setProgress((current) => {
            const next = { ...current }

            if (next[completedAgent]) {
              next[completedAgent] = {
                ...next[completedAgent],
                status:
                  event.status === 'failed'
                    ? 'failed'
                    : 'done',
                confidence: event.confidence ?? null,
                summary: event.summary || '',
              }
            }

            Object.keys(next).forEach((agentKey) => {
              if (next[agentKey].status === 'running') {
                next[agentKey] = {
                  ...next[agentKey],
                  status: 'pending',
                }
              }
            })

            const nextPendingAgent = AGENTS.find(
              (agent) => next[agent.key].status === 'pending',
            )

            if (nextPendingAgent) {
              next[nextPendingAgent.key] = {
                ...next[nextPendingAgent.key],
                status: 'running',
              }
            }

            return next
          })
        }

        if (event.event === 'diagnosis_completed') {
          setDiagnosisRunning(false)

          setProgress((current) =>
            Object.fromEntries(
              AGENTS.map((agent) => [
                agent.key,
                {
                  ...current[agent.key],
                  status:
                    current[agent.key].status === 'pending'
                      ? 'done'
                      : current[agent.key].status,
                },
              ]),
            ),
          )

          fetchIncidentDetails()
        }

        if (event.event === 'diagnosis_failed') {
          setDiagnosisRunning(false)
          setDiagnosisError(
            event.error || 'Diagnosis failed.',
          )
        }

        if (event.event === 'error') {
          setDiagnosisRunning(false)
          setDiagnosisError(
            event.message || 'WebSocket error.',
          )
        }
      } catch {
        setDiagnosisError(
          'Received an invalid progress update from the server.',
        )
      }
    }

    socket.onerror = () => {
      setDiagnosisError(
        'Unable to connect to the diagnosis progress stream.',
      )
      setDiagnosisRunning(false)
    }

    socket.onclose = () => {
      setDiagnosisRunning(false)
    }

    return () => {
      socket.close()
    }
  }, [jobId])

  const fetchIncidentDetails = async () => {
    try {
      const response = await axios.get(
        `http://localhost:8000/api/diagnosis/incidents/${incidentId}`,
        {
          withCredentials: true,
        },
      )

      setIncident(response.data)
    } catch {
      // Keep the currently displayed result if a refresh fails.
    }
  }

  const startDiagnosis = async () => {
    setDiagnosisStarting(true)
    setDiagnosisError('')
    setJobId(null)
    setProgress(createInitialProgress)

    try {
      const response = await axios.post(
        'http://localhost:8000/api/diagnosis',
        {
          incident_id: incidentId,
        },
        {
          withCredentials: true,
        },
      )

      setJobId(response.data.job_id)
      setDiagnosisRunning(true)
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        setDiagnosisError(
          'Your session has expired. Please log in again.',
        )
      } else {
        setDiagnosisError(
          requestError.response?.data?.detail ||
            'Unable to start diagnosis.',
        )
      }

      setDiagnosisRunning(false)
    } finally {
      setDiagnosisStarting(false)
    }
  }

  if (loading) {
    return (
      <section>
        <div className="page-heading">
          <div>
            <h2>Incident Detail</h2>
            <p>Inspect the selected incident and its diagnosis.</p>
          </div>
        </div>

        <div className="content-card">
          <div className="page-loading">
            Loading incident details...
          </div>
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section>
        <div className="page-heading">
          <div>
            <h2>Incident Detail</h2>
            <p>Inspect the selected incident and its diagnosis.</p>
          </div>
        </div>

        <div className="content-card">
          <div className="error-state">
            <strong>Unable to load incident</strong>
            <span>{error}</span>
          </div>

          <Link className="demo-link" to="/incidents">
            Back to incidents
          </Link>
        </div>
      </section>
    )
  }

  const report = incident?.report
  const agentOutputs = incident?.agent_outputs || {}

  const agentContributionData = AGENTS.map((agent) => {
    const output = agentOutputs[agent.key]
    const progressData = progress[agent.key]

    const contribution =
      output?.contribution_weight ??
      output?.contribution ??
      output?.weight ??
      output?.confidence ??
      progressData?.confidence ??
      0

    return {
      name: agent.label.replace(' Agent', ''),
      weight: Number(contribution),
    }
  })

  const metricFindings =
    agentOutputs.metrics_analysis_agent?.findings || []

  const metricAnomalyData = metricFindings
    .filter(
      (finding) =>
        finding.timestamp && finding.value != null,
    )
    .map((finding) => ({
      timestamp: new Date(
        finding.timestamp,
      ).toLocaleTimeString(),
      value: Number(finding.value),
      metric: finding.metric,
      service: finding.service,
      observation: finding.observation,
    }))

  const completedCount = AGENTS.filter(
    (agent) => progress[agent.key].status === 'done',
  ).length

  return (
    <section>
      <div className="page-heading">
        <div>
          <h2>Incident Detail</h2>
          <p>Inspect the selected incident and its diagnosis.</p>
        </div>
      </div>

      <div className="content-card">
        <h3>Incident ID</h3>

        <p className="incident-id">
          {incident?.incident_id}
        </p>

        <h3>Diagnosis Progress</h3>

        <div className="diagnosis-progress">
          <div className="diagnosis-progress-header">
            <strong>
              {completedCount} / {AGENTS.length} agents completed
            </strong>

            <button
              type="button"
              onClick={startDiagnosis}
              disabled={
                diagnosisStarting || diagnosisRunning
              }
            >
              {diagnosisStarting
                ? 'Starting...'
                : diagnosisRunning
                  ? 'Diagnosis Running...'
                  : 'Run Diagnosis'}
            </button>
          </div>

          <div className="agent-progress-list">
            {AGENTS.map((agent) => {
              const agentProgress = progress[agent.key]

              return (
                <div
                  className="agent-progress-item"
                  key={agent.key}
                >
                  <div>
                    <strong>{agent.label}</strong>

                    {agentProgress.summary && (
                      <p>
                        {agentProgress.summary}
                      </p>
                    )}
                  </div>

                  <span
                    className={`agent-status agent-status-${agentProgress.status}`}
                  >
                    {agentProgress.status}
                  </span>
                </div>
              )
            })}
          </div>

          {diagnosisError && (
            <div className="error-state">
              <strong>Diagnosis update</strong>
              <span>{diagnosisError}</span>
            </div>
          )}
        </div>

        <h3>RCA Report</h3>

        {report ? (
          <div>
            <p>
              <strong>Root Cause:</strong>{' '}
              {report.root_cause || '--'}
            </p>

            <div className="confidence-section">
              <strong>Confidence</strong>

              <div className="confidence-chart">
                <ResponsiveContainer
                  width="100%"
                  height={80}
                >
                  <BarChart
                    data={[
                      {
                        name: 'Confidence',
                        value:
                          Number(
                            report.confidence ?? 0,
                          ) * 100,
                      },
                    ]}
                    layout="vertical"
                    margin={{
                      top: 10,
                      right: 20,
                      left: 10,
                      bottom: 10,
                    }}
                  >
                    <XAxis
                      type="number"
                      domain={[0, 100]}
                      tickFormatter={(value) =>
                        `${value}%`
                      }
                    />

                    <YAxis
                      type="category"
                      dataKey="name"
                      hide
                    />

                    <Tooltip
                      formatter={(value) =>
                        `${Number(value).toFixed(1)}%`
                      }
                    />

                    <Bar
                      dataKey="value"
                      name="Confidence"
                      fill="#4f46e5"
                      radius={[0, 6, 6, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="confidence-value">
                {(
                  Number(report.confidence ?? 0) * 100
                ).toFixed(1)}
                %
              </div>
            </div>

            <div className="agent-contribution-section">
              <h4>Agent Contribution Weights</h4>

              <ResponsiveContainer
                width="100%"
                height={280}
              >
                <BarChart
                  data={agentContributionData}
                  layout="vertical"
                  margin={{
                    top: 10,
                    right: 20,
                    left: 20,
                    bottom: 10,
                  }}
                >
                  <CartesianGrid strokeDasharray="3 3" />

                  <XAxis
                    type="number"
                    domain={[0, 1]}
                    tickFormatter={(value) =>
                      Number(value).toFixed(1)
                    }
                  />

                  <YAxis
                    type="category"
                    dataKey="name"
                    width={150}
                  />

                  <Tooltip
                    formatter={(value) =>
                      Number(value).toFixed(3)
                    }
                  />

                  <Bar
                    dataKey="weight"
                    name="Contribution Weight"
                    fill="#6366f1"
                    radius={[0, 6, 6, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {metricAnomalyData.length > 0 && (
              <div className="metric-anomaly-section">
                <h4>Metric Anomalies</h4>

                <div className="metric-anomaly-list">
                  {metricAnomalyData.map((item, index) => (
                    <div
                      className="metric-anomaly-item"
                      key={`${item.metric}-${item.timestamp}-${index}`}
                    >
                      <strong>{item.metric}</strong>

                      <span>
                        {item.service} · {item.timestamp} · Value: {item.value}
                      </span>

                      {item.observation && <p>{item.observation}</p>}

                      {item.relevance && (
                        <p>
                          <strong>Relevance:</strong> {item.relevance}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {report.supporting_evidence && (
              <>
                <h4>Supporting Evidence</h4>

                <pre className="diagnosis-output">
                  {JSON.stringify(
                    report.supporting_evidence,
                    null,
                    2,
                  )}
                </pre>
              </>
            )}
          </div>
        ) : (
          <div className="empty-state">
            <h3>No RCA report yet</h3>

            <p>
              Run a diagnosis for this incident to generate
              the root-cause analysis report.
            </p>
          </div>
        )}

        {incident?.agent_output_ids?.reasoning_agent && (
          <div className="feedback-action">
            <Link
              className="feedback-button"
              to={`/feedback?outputId=${incident.agent_output_ids.reasoning_agent}`}
            >
              Submit Feedback
            </Link>
          </div>
        )}

        <h3>Agent Outputs</h3>

        {Object.keys(agentOutputs).length > 0 ? (
          <pre className="diagnosis-output">
            {JSON.stringify(
              agentOutputs,
              null,
              2,
            )}
          </pre>
        ) : (
          <div className="empty-state">
            <h3>No agent outputs available</h3>

            <p>
              Agent results will appear here after a diagnosis
              has been executed.
            </p>
          </div>
        )}

        <Link
          className="demo-link"
          to="/incidents"
        >
          Back to incidents
        </Link>
      </div>
    </section>
  )
}

export default IncidentDetail