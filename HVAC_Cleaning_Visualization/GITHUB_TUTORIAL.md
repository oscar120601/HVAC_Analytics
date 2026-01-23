# GitHub 新手教學指南 (HVAC 專案)

歡迎！這份文件將手把手教您如何將本專案 (`HVAC_Cleaning_Visualization`) 上傳到您的 GitHub 帳號。

## 第一步：在 GitHub 網站上建立倉庫 (Repository)

1.  登入您的 [GitHub](https://github.com/) 帳號。
2.  點擊右上角的 **"+"** 號，選擇 **"New repository"**。
3.  在 **Repository name** 欄位輸入專案名稱，例如：`HVAC_Analytics`。
4.  **⚠️ 重要**：請確保以下選項**不要勾選** (因為您的電腦裡已經有這些檔案了)：
    -   [ ] Add a README file
    -   [ ] Add .gitignore
    -   [ ] Choose a license
5.  點擊綠色的 **"Create repository"** 按鈕。
6.  建立成功後，您會看到一個頁面，請複製網址 (例如：`https://github.com/您的帳號/HVAC_Analytics.git`)。

---

## 第二步：在您的電腦上設定 Git (只需做一次)

請打開 PowerShell (終端機)，輸入以下兩行指令來告訴 Git 您是誰 (請替換成您的資訊)：

```powershell
git config --global user.name "您的英文名字"
git config --global user.email "您的Email"
```

---

## 第三步：將程式碼上傳 (第一次)

請在 PowerShell 中，依序執行以下指令：

1.  **初始化倉庫** (讓這個資料夾變成 Git 專案)：
    ```powershell
    git init
    ```

2.  **加入檔案** (將所有程式碼加入暫存區)：
    ```powershell
    git add .
    ```
    *(因為我們已經設定了 `.gitignore`，所以敏感的 data 資料夾會自動被略過，不用擔心)*

3.  **提交版本** (就像存檔一樣)：
    ```powershell
    git commit -m "First version: HVAC Dashboard"
    ```

4.  **連結到 GitHub** (請將 `<您的網址>` 換成剛剛複製的網址)：
    ```powershell
    git remote add origin <您的網址>
    ```
    *範例： `git remote add origin https://github.com/oscar-demo/HVAC.git`*

5.  **上傳程式碼**：
    ```powershell
    git branch -M main
    git push -u origin main
    ```
    *(此時可能會跳出視窗要求您登入 GitHub，請依照指示登入即可)*

---

## 第四步：如何在第二台電腦下載？

到了家裡的電腦後：

1.  安裝 Git 與 Python。
2.  打開終端機，執行下載指令：
    ```powershell
    git clone <您的網址>
    ```
3.  進入資料夾：
    ```powershell
    cd HVAC_Analytics
    ```
4.  安裝套件：
    ```powershell
    pip install -r requirements.txt
    ```
5.  **手動把 CSV 資料檔放入 `data/` 資料夾中**。
6.  開始工作！

---

## 常見指令小抄 (Cheatsheet)

-   **檢查狀態** (看看改了什麼)：`git status`
-   **加入修改**：`git add .`
-   **提交修改**：`git commit -m "修改了什麼什麼功能"`
-   **上傳到 GitHub**：`git push`
-   **從 GitHub 下載最新進度**：`git pull`
