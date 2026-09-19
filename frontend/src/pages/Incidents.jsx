import { Link } from 'react-router-dom'

function Incidents() {
  return (
    <section>
      <div className="page-heading">
        <div>
          <h2>Incidents</h2>
          <p>View and investigate system incidents.</p>
        </div>
      </div>

      <div className="content-card">
        <h3>Incident List</h3>
        <p>
          Incident data will be connected to the backend API in the upcoming
          frontend subtasks.
        </p>

        <Link className="demo-link" to="/incidents/demo-incident">
          Open incident detail
        </Link>
      </div>
    </section>
  )
}

export default Incidents
