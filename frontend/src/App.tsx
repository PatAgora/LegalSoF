import { BrowserRouter, Routes, Route } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'
import MattersPage from './pages/MattersPage'
import MatterDetailPage from './pages/MatterDetailPage'
import Layout from './components/Layout'

function App() {
  // Authentication disabled for development - direct access to all pages
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="matters" element={<MattersPage />} />
          <Route path="matters/:id" element={<MatterDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
