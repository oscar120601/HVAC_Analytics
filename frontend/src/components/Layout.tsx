import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import { ConnectionStatus } from './ConnectionStatus'

function Layout() {
  return (
    <div className="flex h-screen w-full bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/20">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        {/* Header with Connection Status */}
        <div className="sticky top-0 z-10 bg-background/80 backdrop-blur-sm border-b px-6 py-3">
          <div className="flex justify-between items-center">
            <h1 className="text-lg font-semibold">HVAC Analytics Dashboard</h1>
            <ConnectionStatus />
          </div>
        </div>
        
        {/* Main Content */}
        <div className="p-6">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  )
}

export default Layout
