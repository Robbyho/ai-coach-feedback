# AI Coach 課程回饋系統

## 系統架構

```
使用者 (瀏覽器打開表單)
    │
    ▼
Render.com (免費 Python Web 主機)
    │
    ├─ /               → survey.html  (學員填寫回饋)
    ├─ /dashboard      → dashboard.html (管理者查看圖表)
    ├─ /api/submit     → POST 儲存回饋
    └─ /api/stats      → GET  統計資料
    │
    ▼
Supabase (免費 PostgreSQL 資料庫)
```

## 一鍵部署

### 步驟 1：建立 Supabase 資料庫（免費，不需信用卡）

1. 到 https://supabase.com 註冊帳號
2. 按 **New project**，填入：
   - Name: `ai-coach-feedback`
   - Database Password: 自設密碼（記下來）
   - Region: 選 Singapore（亞洲）
3. 等 1-2 分鐘完成建立
4. 左側選單 → **Project Settings → Database**
5. 找到 **Connection string** → 複製 `postgresql://...` 整串字串
6. **重要**：把字串中的 `[YOUR-PASSWORD]` 換成你第 2 步設的密碼
7. 打開左側 **SQL Editor** → 貼入 `supabase-setup.sql` 的內容 → 按 **Run**

### 步驟 2：部署到 Render（免費，不需信用卡）

#### 方法 A — 透過 GitHub（推薦）

```bash
# 在終端機執行
cd /mnt/d/ubuntu/ai-coach-feedback
git init
git add .
git commit -m "init feedback system"

# 在 https://github.com 建立一個新 repo 叫 ai-coach-feedback
git remote add origin https://github.com/你的帳號/ai-coach-feedback.git
git branch -M main
git push -u origin main
```

然後：
1. 到 https://dashboard.render.com 註冊（用 GitHub 登入最快）
2. 按 **New + → Web Service**
3. 選你的 `ai-coach-feedback` repo
4. 填寫：
   - Name: `ai-coach-feedback`
   - Environment: **Python 3**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
   - Plan: **Free**
5. 按 **Advanced** → Add Environment Variable:
   - Key: `DATABASE_URL`
   - Value: 貼上步驟 1 的 Supabase 連線字串
6. 按 **Create Web Service**
7. 等 2-3 分鐘部署完成
8. 看到 `https://ai-coach-feedback.onrender.com/` 就完成了！

#### 方法 B — 直接用 Render Dashboard（不需 Git）

1. 到 https://dashboard.render.com 註冊
2. 按 **New + → Web Service**
3. 選 **Upload Files** → 直接把 `app.py`、`requirements.txt`、`static/` 資料夾拖上去
4. 其餘設定同方法 A

### 步驟 3：在 Email 中放入表單連結

部署完成後，你會得到一個網址如：
```
https://ai-coach-feedback.onrender.com/
```

在 AI 教練的 Email 底部加上：

```html
<div style="margin-top:28px;padding:20px;text-align:center;border-top:2px solid #191512;">
  <p style="font-size:16px;color:#4C453D;">📊 你的回饋能讓課程更好</p>
  <a href="https://ai-coach-feedback.onrender.com/"
     style="display:inline-block;background:#D63A0F;color:#F4EFE3;padding:12px 36px;
            border-radius:4px;font-weight:700;font-size:16px;text-decoration:none;">
    🎯 填寫課程回饋（3 分鐘）
  </a>
</div>
```

## 查看回饋儀表板

打開 `https://ai-coach-feedback.onrender.com/dashboard` 即可看到即時分析圖表。

## 注意事項

- **Render 免費方案**：閒置 15 分鐘後會休眠，下一次開啟時需 30-60 秒喚醒，之後恢復正常速度
- **資料安全**：所有回饋資料存於 Supabase 資料庫，不怕重啟遺失
- **成本**：Render + Supabase 免費方案足以服務 50 人團隊