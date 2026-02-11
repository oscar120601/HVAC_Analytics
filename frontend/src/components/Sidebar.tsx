import { useState } from 'react'
import { 
  Factory, 
  Zap, 
  FileText, 
  Brush, 
  BarChart3, 
  LineChart, 
  GitMerge, 
  Target, 
  Download,
  Map,
  Clock,
  TrendingUp,
  History,
  Settings,
  ChevronRight,
  Database
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ProcessingMode, BatchSubPage, OptimizationSubPage } from '@/types'

interface MenuItem {
  id: string
  label: string
  icon: React.ReactNode
  color?: string
}

const batchMenuItems: MenuItem[] = [
  { id: 'batch_parse', label: '解析資料', icon: <FileText size={18} />, color: '#3498db' },
  { id: 'batch_clean', label: '清洗資料', icon: <Brush size={18} />, color: '#e74c3c' },
  { id: 'batch_stats', label: '統計資訊', icon: <BarChart3 size={18} />, color: '#9b59b6' },
  { id: 'batch_timeseries', label: '時間序列', icon: <LineChart size={18} />, color: '#2ecc71' },
  { id: 'batch_correlation', label: '關聯矩陣', icon: <GitMerge size={18} />, color: '#f39c12' },
  { id: 'batch_quality', label: '資料品質', icon: <Target size={18} />, color: '#1abc9c' },
  { id: 'batch_export', label: '匯出', icon: <Download size={18} />, color: '#34495e' },
]

const optimizationMenuItems: MenuItem[] = [
  { id: 'opt_mapping', label: '特徵映射', icon: <Map size={18} />, color: '#e74c3c' },
  { id: 'opt_realtime', label: '即時最佳化', icon: <Zap size={18} />, color: '#3498db' },
  { id: 'opt_importance', label: '特徵重要性', icon: <BarChart3 size={18} />, color: '#9b59b6' },
  { id: 'opt_history', label: '歷史追蹤', icon: <History size={18} />, color: '#2ecc71' },
  { id: 'opt_training', label: '模型訓練', icon: <Settings size={18} />, color: '#f39c12' },
]

function Sidebar() {
  const [mode, setMode] = useState<ProcessingMode>('batch')
  const [currentPage, setCurrentPage] = useState<string>('batch_parse')
  const [fileCount] = useState(214)
  const [modelCount] = useState(5)

  const handleModeChange = (newMode: ProcessingMode) => {
    setMode(newMode)
    setCurrentPage(newMode === 'batch' ? 'batch_parse' : 'opt_mapping')
  }

  const handlePageChange = (pageId: string) => {
    setCurrentPage(pageId)
  }

  const menuItems = mode === 'batch' ? batchMenuItems : optimizationMenuItems
  const themeColor = mode === 'batch' ? '#3498db' : '#e74c3c'

  return (
    <aside className="w-72 h-full bg-white/80 backdrop-blur-xl border-r border-slate-200/60 flex flex-col shadow-xl shadow-slate-200/50">
      {/* Header */}
      <div className="p-6 bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-white/20 rounded-xl backdrop-blur-sm">
            <Factory className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">HVAC Analytics</h1>
            <p className="text-xs text-white/80 font-medium">冰水系統 ETL 工具</p>
          </div>
        </div>
      </div>

      {/* Mode Selection */}
      <div className="px-4 py-4">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 px-2">
          選擇處理模式
        </p>
        <div className="space-y-2">
          {/* Batch Mode Card */}
          <button
            onClick={() => handleModeChange('batch')}
            className={cn(
              "w-full p-4 rounded-xl border-2 transition-all duration-300 text-left group",
              mode === 'batch'
                ? 'border-blue-500 bg-gradient-to-r from-blue-50 to-blue-100/50 shadow-lg shadow-blue-200/50'
                : 'border-slate-200 bg-white hover:border-blue-300 hover:shadow-md'
            )}
          >
            <div className="flex items-center gap-3">
              <div className={cn(
                "p-2.5 rounded-lg transition-colors",
                mode === 'batch' ? 'bg-blue-500 text-white' : 'bg-slate-100 text-slate-600 group-hover:bg-blue-100'
              )}>
                <Database size={20} />
              </div>
              <div>
                <p className={cn(
                  "font-semibold",
                  mode === 'batch' ? 'text-blue-900' : 'text-slate-700'
                )}>批次處理</p>
                <p className="text-xs text-slate-500">資料解析與清洗</p>
              </div>
            </div>
          </button>

          {/* Optimization Mode Card */}
          <button
            onClick={() => handleModeChange('optimization')}
            className={cn(
              "w-full p-4 rounded-xl border-2 transition-all duration-300 text-left group",
              mode === 'optimization'
                ? 'border-red-500 bg-gradient-to-r from-red-50 to-red-100/50 shadow-lg shadow-red-200/50'
                : 'border-slate-200 bg-white hover:border-red-300 hover:shadow-md'
            )}>
            <div className="flex items-center gap-3">
              <div className={cn(
                "p-2.5 rounded-lg transition-colors",
                mode === 'optimization' ? 'bg-red-500 text-white' : 'bg-slate-100 text-slate-600 group-hover:bg-red-100'
              )}>
                <Zap size={20} />
              </div>
              <div>
                <p className={cn(
                  "font-semibold",
                  mode === 'optimization' ? 'text-red-900' : 'text-slate-700'
                )}>最佳化模擬</p>
                <p className="text-xs text-slate-500">能耗預測與優化</p>
              </div>
            </div>
          </button>
        </div>
      </div>

      {/* Divider */}
      <div className="px-6">
        <div className="h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent" />
      </div>

      {/* Sub Menu */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 px-2 flex items-center gap-2">
          <ChevronRight size={14} className="text-slate-300" />
          {mode === 'batch' ? '批次處理選單' : '最佳化模擬選單'}
        </p>
        <nav className="space-y-1">
          {menuItems.map((item) => {
            const isActive = currentPage === item.id
            return (
              <button
                key={item.id}
                onClick={() => handlePageChange(item.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                  isActive
                    ? `bg-gradient-to-r from-${mode === 'batch' ? 'blue' : 'red'}-50 to-transparent text-${mode === 'batch' ? 'blue' : 'red'}-700 border-l-2 border-${mode === 'batch' ? 'blue' : 'red'}-500`
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                )}
                style={{
                  background: isActive ? `${item.color}15` : undefined,
                  color: isActive ? item.color : undefined,
                  borderLeft: isActive ? `3px solid ${item.color}` : '3px solid transparent',
                }}
              >
                <span className={cn(
                  "transition-colors",
                  isActive ? 'text-current' : 'text-slate-400'
                )}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
                {isActive && (
                  <div 
                    className="ml-auto w-1.5 h-1.5 rounded-full"
                    style={{ background: item.color }}
                  />
                )}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Stats Cards */}
      <div className="p-4 space-y-2">
        {mode === 'batch' ? (
          <div className="bg-gradient-to-r from-blue-500/10 to-cyan-500/10 border border-blue-200 rounded-xl p-3">
            <div className="flex items-center gap-2 text-blue-700 mb-1">
              <Database size={16} />
              <span className="text-xs font-semibold uppercase tracking-wider">可用檔案</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-bold text-blue-900">{fileCount}</span>
              <span className="text-sm text-blue-600">個 CSV</span>
            </div>
          </div>
        ) : (
          <div className="bg-gradient-to-r from-red-500/10 to-orange-500/10 border border-red-200 rounded-xl p-3">
            <div className="flex items-center gap-2 text-red-700 mb-1">
              <Settings size={16} />
              <span className="text-xs font-semibold uppercase tracking-wider">已訓練模型</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-bold text-red-900">{modelCount}</span>
              <span className="text-sm text-red-600">個模型</span>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-200">
        <div className="bg-slate-50 rounded-xl p-3 text-center">
          <p className="text-xs font-semibold text-slate-500">HVAC Analytics v3.0</p>
          <p className="text-[10px] text-slate-400 mt-0.5">React + TypeScript + Tailwind</p>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
