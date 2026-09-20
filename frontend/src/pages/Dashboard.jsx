function Dashboard() {
  return (
    <section>
      <div className="page-heading">
        <div>
          <h2>Dashboard</h2>
          <p>Monitor incidents and root cause analysis activity.</p>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <span>Open Incidents</span>
          <strong>—</strong>
        </div>

        <div className="stat-card">
          <span>Active Diagnoses</span>
          <strong>—</strong>
        </div>

        <div className="stat-card">
          <span>Resolved Incidents</span>
          <strong>—</strong>
        </div>

        <div className="stat-card">
          <span>Average Confidence</span>
          <strong>—</strong>
        </div>
      </div>

      <div className="content-card">
        <h3>Adaptive RCA System</h3>

        <p>
          Use the navigation menu to review incidents, inspect diagnosis
          results, and provide feedback to improve the knowledge base.
        </p>
      </div>
    </section>
  )
}

export default Dashboard