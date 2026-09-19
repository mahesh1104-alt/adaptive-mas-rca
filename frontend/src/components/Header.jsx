import { useNavigate } from 'react-router-dom'

function Header() {
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    navigate('/login', { replace: true })
  }

  const storedUser = localStorage.getItem('user')
  let username = 'Engineer'

  if (storedUser) {
    try {
      const user = JSON.parse(storedUser)
      username = user.username || username
    } catch {
      // Ignore invalid local storage data.
    }
  }

  return (
    <header className="header">
      <div>
        <h1>Adaptive Multi-Agent RCA</h1>
        <p>Root Cause Analysis Dashboard</p>
      </div>

      <div className="header-actions">
        <span className="user-name">{username}</span>
        <button type="button" onClick={handleLogout}>
          Logout
        </button>
      </div>
    </header>
  )
}

export default Header
