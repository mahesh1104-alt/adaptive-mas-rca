import { NavLink, useLocation } from 'react-router-dom'

function Sidebar() {
  const location = useLocation()

  const links = [
    { to: '/dashboard', label: 'Dashboard' },
    { to: '/incidents', label: 'Incidents' },
    { to: '/feedback', label: 'Feedback' },
    {
      to: '/feedback/analytics',
      label: 'Feedback Analytics',
    },
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon">R</div>
        <div>
          <h2>Adaptive RCA</h2>
          <span>Incident Intelligence</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {links.map((link) => {
          const isActive = location.pathname === link.to

          return (
            <NavLink
              key={link.to}
              to={link.to}
              className={`nav-link ${isActive ? 'active' : ''}`}
            >
              {link.label}
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}

export default Sidebar
