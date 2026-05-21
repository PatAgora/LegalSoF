import { BrowserRouter, Routes, Route } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'
import MattersPage from './pages/MattersPage'
import MatterDetailPage from './pages/MatterDetailPage'
import LoginPage from './pages/LoginPage'
import ConfigurationPage from './pages/ConfigurationPage'
import ComplianceDashboardPage from './pages/ComplianceDashboardPage'
import ComplianceMattersPage from './pages/ComplianceMattersPage'
import RCADashboardPage from './pages/RCADashboardPage'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="matters" element={<MattersPage />} />
          <Route path="matters/:id" element={<MatterDetailPage />} />
          <Route path="configuration" element={<ConfigurationPage />} />
          <Route path="compliance" element={<ComplianceDashboardPage />} />
          <Route path="compliance/matters" element={<ComplianceMattersPage />} />
          <Route path="rca" element={<RCADashboardPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
