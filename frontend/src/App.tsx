import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import { AppProvider } from './context/AppContext'

function App() {
  return (
    <AppProvider>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
        </Route>
      </Routes>
    </AppProvider>
  )
}

export default App
