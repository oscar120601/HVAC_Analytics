import { useState, useEffect } from 'react'
import { 
  FileText, 
  Brush, 
  BarChart3, 
  LineChart, 
  GitMerge, 
  Target, 
  Download,
  Map,
  Zap,
  History,
  Settings,
  Play,
  CheckCircle2,
  AlertCircle,
  RefreshCw
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import { useListFiles, useParseFiles, useCleanData, useListModels } from '@/hooks/useApi'

// Batch Pages
function ParsePage() {
  const { files, count, loading: filesLoading, listFiles } = useListFiles()
  const { data, loading: parsing, error, parseFiles } = useParseFiles()
  const [selectedFiles, setSelectedFiles] = useState<string[]>([])

  useEffect(() => {
    listFiles()
  }, [listFiles])

  const handleParse = async () => {
    if (selectedFiles.length === 0) {
      // Select all files by default
      await parseFiles(files)
    } else {
      await parseFiles(selectedFiles)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">📋 原始資料解析</h2>
          <p className="text-slate-500 mt-1">解析並合併 CSV 檔案</p>
        </div>
        <Button variant="outline" onClick={() => listFiles()} disabled={filesLoading}>
          <RefreshCw className={cn("w-4 h-4 mr-2", filesLoading && "animate-spin")} />
          重新整理
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className="border-blue-200/60 shadow-lg shadow-blue-100/50">
        <CardHeader className="bg-gradient-to-r from-blue-50/50 to-cyan-50/50">
          <CardTitle className="flex items-center gap-2 text-blue-900">
            <FileText className="w-5 h-5" />
            批次處理設定
          </CardTitle>
          <CardDescription>選擇要解析的檔案範圍</CardDescription>
        </CardHeader>
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center gap-4 p-4 bg-blue-50/50 rounded-lg border border-blue-100">
            <div className="p-3 bg-blue-500 rounded-xl">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="font-semibold text-slate-900">找到 {count} 個檔案</p>
              <p className="text-sm text-slate-500">data/CGMH-TY/*.csv</p>
            </div>
          </div>

          {data && (
            <div className="p-4 bg-green-50 rounded-lg border border-green-200">
              <div className="flex items-center gap-2 text-green-800">
                <CheckCircle2 className="w-5 h-5" />
                <span className="font-medium">解析成功！</span>
              </div>
              <p className="text-sm text-green-700 mt-1">
                總列數: {data.row_count.toLocaleString()} | 
                欄位數: {data.column_count} | 
                欄位: {data.columns?.slice(0, 5).join(', ')}{data.columns?.length > 5 ? '...' : ''}
              </p>
            </div>
          )}

          <Button 
            onClick={handleParse}
            disabled={parsing || filesLoading || count === 0}
            className="w-full bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white shadow-lg shadow-blue-200"
          >
            {parsing ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                解析中...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                解析並合併資料
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Preview Card */}
      <Card>
        <CardHeader>
          <CardTitle>資料預覽</CardTitle>
          <CardDescription>解析後的資料預覽（前 50 筆）</CardDescription>
        </CardHeader>
        <CardContent>
          {data?.preview ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    {data.columns?.map((col: string) => (
                      <th key={col} className="px-3 py-2 text-left font-medium text-slate-700">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.preview.slice(0, 5).map((row: any, i: number) => (
                    <tr key={i} className="border-t">
                      {data.columns?.map((col: string) => (
                        <td key={col} className="px-3 py-2 text-slate-600">
                          {typeof row[col] === 'number' ? row[col].toFixed(2) : String(row[col]).slice(0, 20)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="rounded-lg border bg-slate-50 p-8 text-center">
              <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">尚未解析資料</p>
              <p className="text-sm text-slate-400 mt-1">點擊上方按鈕開始解析</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function CleanPage() {
  const { data, loading, error, cleanData } = useCleanData()

  const handleClean = async () => {
    await cleanData({
      resample_interval: '5m',
      detect_frozen: true,
      apply_steady_state: false,
      apply_heat_balance: false,
      apply_affinity: false,
      filter_invalid: false,
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">🧹 資料清洗</h2>
        <p className="text-slate-500 mt-1">套用資料清洗與物理驗證規則</p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {data && (
        <div className="p-4 bg-green-50 rounded-lg border border-green-200">
          <div className="flex items-center gap-2 text-green-800">
            <CheckCircle2 className="w-5 h-5" />
            <span className="font-medium">清洗完成！</span>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-green-600">原始列數:</span>
              <span className="ml-2 font-medium">{data.original_rows?.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-green-600">清洗後:</span>
              <span className="ml-2 font-medium">{data.cleaned_rows?.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-green-600">保留率:</span>
              <span className="ml-2 font-medium">{data.retention_rate}%</span>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="bg-gradient-to-r from-red-50/50 to-orange-50/50">
            <CardTitle className="flex items-center gap-2 text-red-900">
              <Brush className="w-5 h-5" />
              清洗選項
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6 space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                <span className="text-slate-700">重採樣間隔</span>
                <Badge variant="secondary">5 分鐘</Badge>
              </div>
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                <span className="text-slate-700">檢測凍結資料</span>
                <CheckCircle2 className="w-5 h-5 text-green-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="bg-gradient-to-r from-purple-50/50 to-pink-50/50">
            <CardTitle className="flex items-center gap-2 text-purple-900">
              <Target className="w-5 h-5" />
              物理驗證
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6 space-y-3">
            {[
              { label: '穩態檢測', desc: '只保留負載變化小於 5% 的資料' },
              { label: '熱平衡驗證', desc: '驗證 Q = Flow × ΔT 關係' },
              { label: '親和力定律檢查', desc: '驗證 Power ∝ Frequency³' },
            ].map((item) => (
              <div key={item.label} className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg">
                <div className="w-4 h-4 rounded border-2 border-slate-300 mt-0.5" />
                <div>
                  <p className="font-medium text-slate-700">{item.label}</p>
                  <p className="text-xs text-slate-500">{item.desc}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Button 
        onClick={handleClean}
        disabled={loading}
        className="w-full bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white shadow-lg shadow-red-200"
      >
        {loading ? (
          <>
            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            清洗中...
          </>
        ) : (
          <>
            <Brush className="w-4 h-4 mr-2" />
            開始清洗
          </>
        )}
      </Button>
    </div>
  )
}

// Other batch pages remain similar but simplified
function StatsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">📊 統計資訊</h2>
        <p className="text-slate-500 mt-1">資料欄位統計分析</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: '平均值', value: '123.45', unit: '' },
          { label: '中位數', value: '120.00', unit: '' },
          { label: '標準差', value: '15.67', unit: '' },
        ].map((stat) => (
          <Card key={stat.label} className="bg-gradient-to-br from-white to-slate-50/50">
            <CardContent className="p-6">
              <p className="text-sm text-slate-500 mb-1">{stat.label}</p>
              <p className="text-3xl font-bold text-slate-900">{stat.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function TimeSeriesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">📈 時間序列分析</h2>
        <p className="text-slate-500 mt-1">視覺化資料隨時間的變化趨勢</p>
      </div>

      <Card className="h-[400px] flex items-center justify-center">
        <div className="text-center">
          <LineChart className="w-16 h-16 text-slate-200 mx-auto mb-4" />
          <p className="text-slate-500">請先解析資料以查看時間序列</p>
        </div>
      </Card>
    </div>
  )
}

function CorrelationPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">🔗 關聯矩陣熱圖</h2>
        <p className="text-slate-500 mt-1">分析變數間的相關性</p>
      </div>

      <Card className="h-[500px] flex items-center justify-center">
        <div className="text-center">
          <GitMerge className="w-16 h-16 text-slate-200 mx-auto mb-4" />
          <p className="text-slate-500">請選擇變數以生成關聯矩陣</p>
        </div>
      </Card>
    </div>
  )
}

function QualityPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">🎯 資料品質儀表板</h2>
        <p className="text-slate-500 mt-1">全面評估資料品質指標</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: '總列數', value: '0', color: 'blue' },
          { label: '總欄位數', value: '0', color: 'purple' },
          { label: '數值欄位', value: '0', color: 'green' },
          { label: '品質評分', value: '-', color: 'orange' },
        ].map((stat) => (
          <Card key={stat.label}>
            <CardContent className="p-4">
              <p className="text-xs text-slate-500 uppercase tracking-wider">{stat.label}</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{stat.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function ExportPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">💾 匯出資料</h2>
        <p className="text-slate-500 mt-1">下載處理後的資料</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>CSV 格式</CardTitle>
            <CardDescription>通用格式，相容性最佳</CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full" variant="outline">
              <Download className="w-4 h-4 mr-2" />
              下載 CSV
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Parquet 格式</CardTitle>
            <CardDescription>高效能格式，適合大型資料集</CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full" variant="outline">
              <Download className="w-4 h-4 mr-2" />
              下載 Parquet
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// Optimization Pages with real API
function MappingPage() {
  const { models, loading, listModels } = useListModels()

  useEffect(() => {
    listModels()
  }, [listModels])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">🗺️ 特徵映射配置</h2>
        <p className="text-slate-500 mt-1">將資料欄位對應到模型特徵類別</p>
      </div>

      <Card>
        <CardHeader className="bg-gradient-to-r from-red-50/50 to-pink-50/50">
          <CardTitle className="text-red-900">已訓練模型</CardTitle>
          <CardDescription>選擇要使用的模型</CardDescription>
        </CardHeader>
        <CardContent className="p-6">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="w-6 h-6 animate-spin text-slate-400" />
            </div>
          ) : models.length > 0 ? (
            <div className="space-y-2">
              {models.map((model: any) => (
                <div key={model.name} className="p-3 bg-slate-50 rounded-lg flex justify-between items-center">
                  <div>
                    <p className="font-medium text-slate-900">{model.name}</p>
                    <p className="text-xs text-slate-500">
                      MAPE: {model.mape?.toFixed(2) ?? '-'}% | 
                      R²: {model.r2?.toFixed(4) ?? '-'} | 
                      特徵: {model.feature_count}
                    </p>
                  </div>
                  <Button size="sm">選擇</Button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Settings className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">尚未訓練模型</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Button className="bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white">
        <Zap className="w-4 h-4 mr-2" />
        自動識別
      </Button>
    </div>
  )
}

function RealtimePage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">🎯 即時最佳化</h2>
        <p className="text-slate-500 mt-1">計算最佳的變頻器設定組合</p>
      </div>

      <Card className="p-12 text-center">
        <Zap className="w-16 h-16 text-slate-200 mx-auto mb-4" />
        <p className="text-slate-500">請先完成特徵映射配置</p>
      </Card>
    </div>
  )
}

function ImportancePage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">📊 特徵重要性分析</h2>
        <p className="text-slate-500 mt-1">查看模型各特徵的重要性權重</p>
      </div>

      <Card className="h-[400px] flex items-center justify-center">
        <BarChart3 className="w-16 h-16 text-slate-200" />
      </Card>
    </div>
  )
}

function HistoryPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">📈 最佳化歷史追蹤</h2>
        <p className="text-slate-500 mt-1">查看歷史最佳化記錄</p>
      </div>

      <Card className="p-12 text-center">
        <History className="w-16 h-16 text-slate-200 mx-auto mb-4" />
        <p className="text-slate-500">暫無最佳化歷史記錄</p>
      </Card>
    </div>
  )
}

function TrainingPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">🔧 模型訓練</h2>
        <p className="text-slate-500 mt-1">訓練新的能耗預測模型</p>
      </div>

      <Card className="p-8">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-amber-100 rounded-lg">
            <AlertCircle className="w-6 h-6 text-amber-600" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">訓練流程</h3>
            <ol className="mt-2 space-y-2 text-sm text-slate-600 list-decimal list-inside">
              <li>切換到「批次處理」模式</li>
              <li>解析並清洗資料</li>
              <li>配置特徵映射</li>
              <li>訓練模型</li>
            </ol>
          </div>
        </div>
      </Card>
    </div>
  )
}

// Main Dashboard
function Dashboard() {
  const [currentPage] = useState('batch_parse')

  const renderPage = () => {
    switch (currentPage) {
      // Batch pages
      case 'batch_parse': return <ParsePage />
      case 'batch_clean': return <CleanPage />
      case 'batch_stats': return <StatsPage />
      case 'batch_timeseries': return <TimeSeriesPage />
      case 'batch_correlation': return <CorrelationPage />
      case 'batch_quality': return <QualityPage />
      case 'batch_export': return <ExportPage />
      // Optimization pages
      case 'opt_mapping': return <MappingPage />
      case 'opt_realtime': return <RealtimePage />
      case 'opt_importance': return <ImportancePage />
      case 'opt_history': return <HistoryPage />
      case 'opt_training': return <TrainingPage />
      default: return <ParsePage />
    }
  }

  return (
    <div className="animate-fade-in">
      {renderPage()}
    </div>
  )
}

export default Dashboard
