import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import axios from 'axios'

function ProtectedRoute() {
  const location = useLocation()
  const [checking, setChecking] = useState(true)
  const [authenticated, setAuthenticated] = useState(false)

  useEffect(() => {
    let mounted = true

    const checkAuthentication = async () => {
      try {
        await axios.get(
          'http://localhost:8000/api/auth/me',
          {
            withCredentials: true,
          },
        )

        if (mounted) {
          setAuthenticated(true)
        }
      } catch {
        if (mounted) {
          setAuthenticated(false)
        }
      } finally {
        if (mounted) {
          setChecking(false)
        }
      }
    }

    checkAuthentication()

    return () => {
      mounted = false
    }
  }, [])

  if (checking) {
    return <div className="page-loading">Checking authentication...</div>
  }

  if (!authenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location }}
      />
    )
  }

  return <Outlet />
}

export default ProtectedRoute
