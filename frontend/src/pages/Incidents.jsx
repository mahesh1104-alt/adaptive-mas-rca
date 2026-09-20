import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'

const ITEMS_PER_PAGE = 10

function Incidents() {
  const [incidents, setIncidents] = useState([])
  const [statusFilter, setStatusFilter] = useState('all')
  const [serviceFilter, setServiceFilter] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchIncidents = async () => {
      setLoading(true)
      setError('')

      try {
        const token = localStorage.getItem('access_token')

        const response = await axios.get(
          'http://localhost:8000/api/incidents',
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          },
        )

        setIncidents(response.data)
      } catch (requestError) {
        if (requestError.response?.status === 401) {
          setError('Your session has expired. Please log in again.')
        } else {
          setError('Unable to load incidents from the backend.')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchIncidents()
  }, [])

  const statuses = useMemo(() => {
    return [
      'all',
      ...new Set(
        incidents
          .map((incident) => incident.status)
          .filter(Boolean),
      ),
    ]
  }, [incidents])

  const services = useMemo(() => {
    return [
      'all',
      ...new Set(
        incidents
          .map((incident) => incident.source)
          .filter(Boolean),
      ),
    ]
  }, [incidents])

  const filteredIncidents = useMemo(() => {
    return incidents.filter((incident) => {
      const matchesStatus =
        statusFilter === 'all' || incident.status === statusFilter

      const matchesService =
        serviceFilter === 'all' || incident.source === serviceFilter

      return matchesStatus && matchesService
    })
  }, [incidents, statusFilter, serviceFilter])

  const totalPages = Math.max(
    1,
    Math.ceil(filteredIncidents.length / ITEMS_PER_PAGE),
  )

  const paginatedIncidents = filteredIncidents.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE,
  )

  const handleStatusChange = (event) => {
    setStatusFilter(event.target.value)
    setCurrentPage(1)
  }

  const handleServiceChange = (event) => {
    setServiceFilter(event.target.value)
    setCurrentPage(1)
  }

  const formatTimestamp = (timestamp) => {
    if (!timestamp) {
      return '--'
    }

    return new Date(timestamp).toLocaleString()
  }

  return (
    <section>
      <div className="page-heading">
        <div>
          <h2>Incidents</h2>
          <p>View and investigate system incidents.</p>
        </div>
      </div>

      <div className="content-card">
        <div className="incident-toolbar">
          <div className="filter-group">
            <label htmlFor="status-filter">Status</label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={handleStatusChange}
            >
              {statuses.map((status) => (
                <option key={status} value={status}>
                  {status === 'all' ? 'All statuses' : status}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="service-filter">Service</label>
            <select
              id="service-filter"
              value={serviceFilter}
              onChange={handleServiceChange}
            >
              {services.map((service) => (
                <option key={service} value={service}>
                  {service === 'all' ? 'All services' : service}
                </option>
              ))}
            </select>
          </div>
        </div>

        {loading && (
          <div className="table-message">
            Loading incidents...
          </div>
        )}

        {!loading && error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {!loading && !error && filteredIncidents.length === 0 && (
          <div className="table-message">
            No incidents found for the selected filters.
          </div>
        )}

        {!loading && !error && filteredIncidents.length > 0 && (
          <>
            <div className="incident-table-wrapper">
              <table className="incident-table">
                <thead>
                  <tr>
                    <th>Incident</th>
                    <th>Status</th>
                    <th>Service</th>
                    <th>Severity</th>
                    <th>Created</th>
                  </tr>
                </thead>

                <tbody>
                  {paginatedIncidents.map((incident) => (
                    <tr key={incident.incident_id}>
                      <td>
                        <Link
                          className="incident-link"
                          to={`/incidents/${incident.incident_id}`}
                        >
                          <strong>{incident.title}</strong>
                          <span>{incident.incident_id}</span>
                        </Link>
                      </td>

                      <td>
                        <span className="status-badge">
                          {incident.status}
                        </span>
                      </td>

                      <td>
                        {incident.source || '--'}
                      </td>

                      <td>
                        {incident.severity}
                      </td>

                      <td>
                        {formatTimestamp(incident.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <span>
                Showing{' '}
                {(currentPage - 1) * ITEMS_PER_PAGE + 1}
                {' - '}
                {Math.min(
                  currentPage * ITEMS_PER_PAGE,
                  filteredIncidents.length,
                )}{' '}
                of {filteredIncidents.length}
              </span>

              <div className="pagination-controls">
                <button
                  type="button"
                  onClick={() =>
                    setCurrentPage((page) => Math.max(1, page - 1))
                  }
                  disabled={currentPage === 1}
                >
                  Previous
                </button>

                <span>
                  Page {currentPage} of {totalPages}
                </span>

                <button
                  type="button"
                  onClick={() =>
                    setCurrentPage((page) =>
                      Math.min(totalPages, page + 1),
                    )
                  }
                  disabled={currentPage === totalPages}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  )
}

export default Incidents