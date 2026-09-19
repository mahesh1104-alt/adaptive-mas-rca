import { NavLink } from 'react-router-dom'

function Sidebar() {
  const links = [
    { to: '/dashboard', label: 'Dashboard' },
    { to: '/incidents', label: 'Incidents' },
    { to: '/feedback', label: 'Feedback' },
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
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              `nav-link ${isActive ? 'active' : ''}`
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}

export default Sidebar
