import { BrowserRouter, Routes, Route } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'
import MattersPage from './pages/MattersPage'
import MatterDetailPage from './pages/MatterDetailPage'
import LoginPage from './pages/LoginPage'
import ConfigurationPage from './pages/ConfigurationPage'
import SettingsPage from './pages/SettingsPage'
import ComplianceDashboardPage from './pages/ComplianceDashboardPage'
import ComplianceMattersPage from './pages/ComplianceMattersPage'
import RCADashboardPage from './pages/RCADashboardPage'
import PortalUploadPage from './pages/PortalUploadPage'
import FirmRiskAssessmentPage from './pages/FirmRiskAssessmentPage'
import MatterRiskAssessmentPage from './pages/MatterRiskAssessmentPage'
import KybPage from './pages/KybPage'
import EidvPage from './pages/EidvPage'
import MlroPage from './pages/MlroPage'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        {/* Public client evidence-upload portal — no auth, no Layout. */}
        <Route path="/portal/:token" element={<PortalUploadPage />} />
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
          <Route path="matters/:matterId/risk-assessment" element={<MatterRiskAssessmentPage />} />
          <Route path="matters/:matterId/kyb" element={<KybPage />} />
          <Route path="matters/:matterId/eidv" element={<EidvPage />} />
          <Route path="mlro" element={<AdminRoute><MlroPage /></AdminRoute>} />
          <Route path="firm-risk-assessment" element={<AdminRoute><FirmRiskAssessmentPage /></AdminRoute>} />
          <Route path="settings" element={<SettingsPage />} />
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
