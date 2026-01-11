import { Outlet, Link } from 'react-router-dom'

export default function Layout() {
  // Authentication disabled for development
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/" className="flex items-center">
                <img src="/forbes-logo.png" alt="Forbes Solicitors" className="h-10" />
              </Link>
              <div className="hidden sm:ml-8 sm:flex sm:space-x-8">
                <Link
                  to="/"
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-900 border-b-2 border-primary-500"
                >
                  Dashboard
                </Link>
                <Link
                  to="/matters"
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900 border-b-2 border-transparent hover:border-gray-300"
                >
                  Matters
                </Link>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <img src="/more-than-law-logo-clean.png" alt="More than law" className="h-12" />
              <div className="text-sm text-gray-700">
                <span className="font-medium">Development Mode</span>
                <span className="ml-2 px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs">No Auth</span>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}
