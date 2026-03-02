# Excel 範本錯誤修復總結

## 🐛 問題描述

Excel 開啟產生的範本時出現以下錯誤：
- 「Excel 無法藉由修復或移除無法讀取的內容來開啟檔案」
- 「已移除的記錄: /xl/worksheets/sheet1.xml 部分的公式」
- 下拉選單顯示異常

## 🔧 修復過程

### 嘗試 1：修正公式格式
- 將 `=ValidValues!$A$1:$A$19` 改為 `ValidValues!A1:A19`
- **結果**：仍報錯

### 嘗試 2：使用 LibreOffice 格式
- 將 `ValidValues!A1:A19` 改為 `=$ValidValues.$A$1:$A$19`
- **結果**：仍報錯

### 嘗試 3：顯示 ValidValues 分頁
- 移除 `ws_valid.sheet_state = 'veryHidden'`
- **結果**：仍報錯

### 嘗試 4：使用字串清單（最終解決方案）✅
- 將 DataValidation 從「範圍引用」改為「字串清單」
- 例如：`"temperature,pressure,energy,gauge"`
- **結果**：Excel 正常開啟，無錯誤訊息

## ✅ 最終解決方案

### 修改檔案
`tools/features/wizard.py`

### 修改內容
```python
# 修復前（導致錯誤）
dv = DataValidation(type="list", formula1='ValidValues!A1:A19')

# 修復後（正常運作）
dv = DataValidation(type="list", formula1='"temperature,pressure,energy,gauge"')
```

### 受影響的欄位
| 欄位 | 下拉選單內容 |
|:---|:---|
| physical_type | temperature,pressure,flow_rate,power,chiller_load,status,gauge,cooling_capacity,efficiency,energy,valve_position,frequency,rotational_speed,current,voltage,power_factor,pressure_differential,operating_status,temporal |
| device_role | primary,backup,seasonal |
| is_target | TRUE,FALSE |
| enable_lag | TRUE,FALSE |
| status | pending_review,confirmed,deprecated |
| control_semantic | on_off,variable_speed,valve_position,setpoint,feedback,none |

## 📋 變更摘要

1. **DataValidation 公式格式**：改為使用字串清單而非工作表範圍引用
2. **ValidValues 分頁**：保留作為參考（存放中文說明），但下拉選單不再引用它
3. **Instructions 說明**：更新相關說明文字，移除引用 ValidValues 的內容

## 📝 注意事項

- **ValidValues 分頁現在會顯示**：使用者可以看到下拉選單的所有選項及其中文說明
- **下拉選單功能正常**：點擊儲存格會顯示正確的下拉選項
- **Excel 相容性**：此修改確保與所有版本的 Excel 相容

## ✅ 驗證結果

- [x] Excel 開啟無錯誤訊息
- [x] 下拉選單正常顯示
- [x] 所有選項可正常選擇
- [x] 檔案可正常儲存

---

**修復日期**: 2026-03-02  
**版本**: v1.6.1-patch1  
**負責人**: AI Assistant
