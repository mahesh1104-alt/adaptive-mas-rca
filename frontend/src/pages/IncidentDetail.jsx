import { Link, useParams } from 'react-router-dom'

function IncidentDetail() {
  const { incidentId } = useParams()

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
        <p className="incident-id">{incidentId}</p>

        <p>
          Detailed incident information and RCA results will be connected to
          the backend in the upcoming frontend subtasks.
        </p>

        <Link className="demo-link" to="/incidents">
          Back to incidents
        </Link>
      </div>
    </section>
  )
}

export default IncidentDetail
