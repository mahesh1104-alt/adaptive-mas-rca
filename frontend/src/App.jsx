import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import DashboardLayout from './layouts/DashboardLayout'
import Dashboard from './pages/Dashboard'
import Feedback from './pages/Feedback'
import IncidentDetail from './pages/IncidentDetail'
import Incidents from './pages/Incidents'
import Login from './pages/Login'
import './App.css'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<DashboardLayout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/incidents" element={<Incidents />} />
          <Route
            path="/incidents/:incidentId"
            element={<IncidentDetail />}
          />
          <Route path="/feedback" element={<Feedback />} />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
