import { createContext, useContext, useState, ReactNode } from 'react'

export type ProcessingMode = 'batch' | 'optimization'

interface AppContextType {
  mode: ProcessingMode
  setMode: (mode: ProcessingMode) => void
  currentPage: string
  setCurrentPage: (page: string) => void
}

const AppContext = createContext<AppContextType | undefined>(undefined)

export function AppProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ProcessingMode>('batch')
  const [currentPage, setCurrentPage] = useState<string>('batch_parse')

  const handleSetMode = (newMode: ProcessingMode) => {
    setMode(newMode)
    // Reset to default page when mode changes
    setCurrentPage(newMode === 'batch' ? 'batch_parse' : 'opt_mapping')
  }

  return (
    <AppContext.Provider value={{ mode, setMode: handleSetMode, currentPage, setCurrentPage }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useApp must be used within AppProvider')
  }
  return context
}
