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
import AdminRoute from './components/AdminRoute'

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
          <Route path="configuration" element={<AdminRoute><ConfigurationPage /></AdminRoute>} />
          <Route path="compliance" element={<AdminRoute><ComplianceDashboardPage /></AdminRoute>} />
          <Route path="compliance/matters" element={<AdminRoute><ComplianceMattersPage /></AdminRoute>} />
          <Route path="rca" element={<AdminRoute><RCADashboardPage /></AdminRoute>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
