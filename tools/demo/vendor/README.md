# Demo Vendor Dependencies

此目錄包含 Sprint 2 Demo 所需的第三方 JavaScript 函式庫，確保離線環境仍可正常展示。

## 檔案清單

| 檔案 | 版本 | 來源 | 用途 |
|:---|:---:|:---|:---|
| `chart.umd.min.js` | 4.4.0 | jsdelivr CDN | Chart.js 圖表繪製（雷達圖） |
| `mermaid.min.js` | 10.6.1 | jsdelivr CDN | Mermaid 流程圖渲染 |

## 版本鎖定

- Chart.js: `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`
- Mermaid: `https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js`

## 更新方式

如需更新版本：

```powershell
# 下載新版 Chart.js
Invoke-WebRequest -Uri "https://cdn.jsdelivr.net/npm/chart.js@X.X.X/dist/chart.umd.min.js" -OutFile "chart.umd.min.js"

# 下載新版 Mermaid
Invoke-WebRequest -Uri "https://cdn.jsdelivr.net/npm/mermaid@X.X.X/dist/mermaid.min.js" -OutFile "mermaid.min.js"
```

## 離線使用

BAS 案場常見網路隔離環境，Demo 檔案已改為引用本地 vendor 檔案：

```html
<!-- 修改前：CDN 引用 -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<!-- 修改後：本地引用 -->
<script src="vendor/chart.umd.min.js"></script>
```

---

最後更新: 2026-02-24
