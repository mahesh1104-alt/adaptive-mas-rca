import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import axios from 'axios'

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
        const token = localStorage.getItem('access_token')

        const response = await axios.get(
          `http://localhost:8000/api/diagnosis/incidents/${incidentId}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
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

    const token = localStorage.getItem('access_token')

    if (!token) {
      setDiagnosisError('Your session has expired. Please log in again.')
      setDiagnosisRunning(false)
      return undefined
    }

    const socket = new WebSocket(
      `ws://localhost:8000/api/diagnosis/ws/${jobId}?token=${encodeURIComponent(token)}`,
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

            // Only one agent should be running at a time.
            Object.keys(next).forEach((agentKey) => {
              if (next[agentKey].status === 'running') {
                next[agentKey] = {
                  ...next[agentKey],
                  status: 'pending',
                }
              }
            })

            // Make the first remaining pending agent the active one.
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
      const token = localStorage.getItem('access_token')

      const response = await axios.get(
        `http://localhost:8000/api/diagnosis/incidents/${incidentId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
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
      const token = localStorage.getItem('access_token')

      const response = await axios.post(
        'http://localhost:8000/api/diagnosis',
        {
          incident_id: incidentId,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
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
          <div className="table-message">
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
          <div className="error-message">
            {error}
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
            <div className="error-message">
              {diagnosisError}
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

            <p>
              <strong>Confidence:</strong>{' '}
              {report.confidence ?? '--'}
            </p>

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
          <p>
            No RCA report is available for this incident yet.
          </p>
        )}

        <h3>Agent Outputs</h3>

        {Object.keys(agentOutputs).length > 0 ? (
          <pre className="diagnosis-output">
            {JSON.stringify(agentOutputs, null, 2)}
          </pre>
        ) : (
          <p>
            No agent outputs are available for this incident yet.
          </p>
        )}

        <Link className="demo-link" to="/incidents">
          Back to incidents
        </Link>
      </div>
    </section>
  )
}

export default IncidentDetail
