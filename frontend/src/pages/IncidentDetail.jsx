import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import axios from 'axios'

function IncidentDetail() {
  const { incidentId } = useParams()

  const [incident, setIncident] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

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
        <p className="incident-id">{incident?.incident_id}</p>

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
          <p>No RCA report is available for this incident yet.</p>
        )}

        <h3>Agent Outputs</h3>

        {Object.keys(agentOutputs).length > 0 ? (
          <pre className="diagnosis-output">
            {JSON.stringify(agentOutputs, null, 2)}
          </pre>
        ) : (
          <p>No agent outputs are available for this incident yet.</p>
        )}

        <Link className="demo-link" to="/incidents">
          Back to incidents
        </Link>
      </div>
    </section>
  )
}

export default IncidentDetail