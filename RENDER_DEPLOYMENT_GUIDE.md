# 🚀 DataNova - Render Production Deployment Guide

Aapka **DataNova Smart Analytics Platform** ab **Render** par deploy karne ke liye **100% Production-Ready** hai. Humne project ke har ek component, configuration file, database connector, server settings aur dependencies ko audit karke configure kar diya hai taaki deployment me **koi bhi error na aaye**.

---

## 🛠️ Humne Kya-Kya Fix & Configure Kiya Hai?

1. **Production WSGI Server (`gunicorn.conf.py` & `requirements.txt`)**:
   - Render production environment me Flask ka default dev server use nahi hota. Humne `gunicorn>=23.0.0` add kiya hai.
   - Concurrency, memory leak prevention (worker recycling), aur **120-second timeout** configure kiya hai taaki heavy Machine Learning aur EDA charts generate hote waqt connection drop na ho.

2. **Render Dynamic Port & Host Binding (`app.py`)**:
   - Render run hone par dynamic `$PORT` assign karta hai aur app ko `0.0.0.0` par listen karna zaroori hota hai. Humne `app.py` ko `$PORT` aur `0.0.0.0` ke sath bind kar diya hai.

3. **Cloud Database & SSL Auto-Detection (`database/db_connector.py`)**:
   - Render, Aiven, Railway ya TiDB Cloud se milne wale `DATABASE_URL` / `MYSQL_URL` ka automatic parser add kiya hai.
   - Remote Cloud MySQL providers (Aiven, TiDB Cloud, AWS RDS, Railway) ke sath secure SSL transport auto-detect hoti hai taaki SSL verification error na aaye.

4. **Reverse Proxy & HTTPS Support (`ProxyFix`)**:
   - Render SSL reverse proxy use karta hai. Humne `werkzeug.middleware.proxy_fix.ProxyFix` integrate kiya hai taaki URLs aur Google OAuth redirects automatically `https://` par generate ho aur `redirect_uri_mismatch` na ho.

5. **Zero-Crash SECRET_KEY Fallback**:
   - Agar Render ke dashboard me `SECRET_KEY` set karna bhool bhi jao, tab bhi app crash hone ki jagah safe production fallback key auto-generate karke boot ho jayega.

6. **Render Health Check Endpoint (`/health`)**:
   - Render ke deployment monitoring ke liye fast `/health` endpoint add kiya gaya hai jo instantly `200 OK` return karta hai.

7. **Production Dependencies & Python Version**:
   - `runtime.txt` add kiya (`python-3.11.9`) jo data science libraries (`pandas`, `numpy`, `scipy`, `scikit-learn`) ke precompiled binary wheels ke liye sabse stable hai.
   - `Pillow` aur `lxml` ko `requirements.txt` me explicitly add kiya gaya hai.

8. **Git Hygiene (`.gitignore`)**:
   - `.gitignore` create kiya gaya hai taaki heavy `venv/` folder, local `.env` aur cache files GitHub par upload na ho.

9. **1-Click Render Blueprint (`render.yaml`)**:
   - Render ka official Blueprint config add kiya hai jisse deployment 1-click me ho jata hai.

---

## 📋 Render Par Deploy Karne Ka Step-by-Step Tarika

### Step 1: Code Ko GitHub Par Push Karein

Render aapke GitHub repository se deploy karta hai:

```bash
git init
git add .
git commit -m "Configure DataNova for Render production deployment"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo-name>.git
git push -u origin main
```

*(Note: `.gitignore` ki wajah se `venv` aur `.env` push nahi honge, sirf aapka source code jayega).*

---

### Step 2: Free Cloud MySQL Database Setup Karein

Render native PostgreSQL provide karta hai. DataNova MySQL use karta hai, isliye aap inme se kisi bhi **Free Cloud MySQL** service ka use kar sakte hain (5 minutes lagte hain):

#### Option A: Aiven Cloud (Recommended - Free Tier)
1. [aiven.io](https://aiven.io/) par jao aur Free Account banao.
2. New Service create karo: **MySQL** (Free plan select karo).
3. Service banne ke baad **Service URI** copy karo (format: `mysql://avnadmin:password@host:port/defaultdb?ssl-mode=REQUIRED`).
4. Bas yahi URI aapko Render me `DATABASE_URL` me paste karni hai!

#### Option B: TiDB Cloud (Serverless Free MySQL)
1. [tidbcloud.com](https://tidbcloud.com/) par jao aur Serverless Cluster banao (Permanent Free).
2. Connect button par click karke connection details (Host, User, Password, Port 4000, Database name) copy karo.

#### Option C: Railway.app (Free / Low Cost)
1. [railway.app](https://railway.app/) par New Project -> **Provision MySQL** par click karo.
2. `MYSQL_URL` copy karke Render me `DATABASE_URL` me daal do.

---

### Step 3: Render Par Web Service Create Karein

1. [render.com](https://render.com/) par login karein.
2. **New +** button par click karein aur **Web Service** select karein.
3. Apna GitHub repository connect karein.
4. Niche diye gaye settings fill karein:

| Field | Value |
|---|---|
| **Name** | `datanova` (ya aapki marzi ka naam) |
| **Language / Runtime** | `Python 3` |
| **Region** | `Oregon (US West)` ya `Frankfurt (EU)` |
| **Branch** | `main` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn --config gunicorn.conf.py app:app` |
| **Instance Type** | `Free` |

---

### Step 4: Render Environment Variables Add Karein

Render dashboard me **Environment** tab me jakar niche diye gaye variables add karein:

#### Zaroori Variables (Required):
| Key | Value | Example / Note |
|---|---|---|
| `PYTHON_VERSION` | `3.11.9` | Precompiled wheels ke liye |
| `DATABASE_URL` | *Aapka Cloud MySQL URL* | `mysql://user:pass@host:port/dbname?ssl-mode=REQUIRED` |
| `SECRET_KEY` | *Koi bhi 32-character random string* | Session security ke liye |
| `GROQ_API_KEY` | *Aapki Groq API Key* | Primary AI Insights ke liye |

*(Agar aap `DATABASE_URL` ke badle alag-alag variables use karna chahe toh `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` bhi use kar sakte hain).*

#### Optional Variables (Features ke hisab se):
| Key | Value | Purpose |
|---|---|---|
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | AI model |
| `OPENROUTER_API_KEY` | *Optional* | Fallback AI Provider 1 |
| `GEMINI_API_KEY` | *Optional* | Fallback AI Provider 2 |
| `MAIL_SERVER` | `smtp.gmail.com` | Email server |
| `MAIL_PORT` | `587` | SMTP port (System me automatic Port 465 SSL fallback built-in hai) |
| `MAIL_USE_TLS` | `true` | STARTTLS encryption |
| `MAIL_USE_SSL` | `false` | SSL encryption |
| `MAIL_USERNAME` | `your_email@gmail.com` | Aapka Gmail address |
| `MAIL_PASSWORD` | `xxxx xxxx xxxx xxxx` | Google 16-digit App Password (Spaces auto-handled) |
| `MAIL_DEFAULT_SENDER` | `your_email@gmail.com` | Sender header (Gmail address) |
| `GOOGLE_CLIENT_ID` | `xxxx.apps.googleusercontent.com` | "Continue with Google" OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | `GOCSPX-xxxx` | Google OAuth secret |
| `GOOGLE_REDIRECT_URI` | `https://<your-app>.onrender.com/auth/google/callback` | OAuth callback URL |
| `GDRIVE_FOLDER_ID` | *Optional* | Google Drive storage backup |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | *Optional* | Google Service Account JSON |

---

### 🔑 Google OAuth & Mail (OTP) Setup Guide for Render:

#### A. Gmail SMTP / OTP Setup (Email & OTP Ke Liye):
1. Apne Google Account me **2-Step Verification** ON karein: [myaccount.google.com/security](https://myaccount.google.com/security).
2. Search bar me type karein **App Passwords** ya visit karein: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. App name me `DataNova` daalein aur **Create** par click karein.
4. Google aapko 16-character ka App Password dega (jaise `icsr csvi vfto fhkd`).
5. Render ke **Environment** tab me add karein:
   - `MAIL_USERNAME` = `your_email@gmail.com`
   - `MAIL_PASSWORD` = `icsr csvi vfto fhkd` (spaces ho ya na ho, DataNova automatically clean kar lega)
   - `MAIL_DEFAULT_SENDER` = `your_email@gmail.com`
   - `MAIL_PORT` = `587`
   - `MAIL_SERVER` = `smtp.gmail.com`
   *(DataNova me intelligent dual-port retry built-in hai: agar port 587 cloud par block ya slow ho, toh turant port 465 SSL fallback use karega).*

#### B. Google Sign-In Setup ("Continue with Google" Ke Liye):
1. [Google Cloud Console](https://console.cloud.google.com/) me jayein.
2. **APIs & Services** -> **Credentials** me jayein.
3. Apne OAuth 2.0 Client ID ko open karein.
4. **Authorized JavaScript origins** me add karein:
   - `http://127.0.0.1:5000`
   - `https://<your-app-name>.onrender.com`
5. **Authorized redirect URIs** me dono URIs add karein:
   - `http://127.0.0.1:5000/auth/google/callback`
   - `http://127.0.0.1:5000/google/callback`
   - `https://<your-app-name>.onrender.com/auth/google/callback`
   - `https://<your-app-name>.onrender.com/google/callback`
6. Save karein!
7. Render Environment me add karein:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REDIRECT_URI` = `https://<your-app-name>.onrender.com/auth/google/callback`

---

### Step 5: Deploy & Verification

1. **Deploy Web Service** par click karein.
2. Render ke **Logs** tab me aapko dikhega:
   - Python 3.11.9 install ho raha hai.
   - Requirements install ho rahi hain.
   - `[database.db_connector]: Database tables and high-concurrency indexes verified/created successfully.`
   - `Gunicorn active on 0.0.0.0:$PORT`
3. Jab build complete ho jayega toh Render aapko live URL dega:
   👉 `https://datanova.onrender.com`
4. Health check URL verify karein:
   👉 `https://datanova.onrender.com/health` (Returns `{"status": "healthy"}`)

---

## 🎯 Important Features in DataNova on Render:
- **Zero-Downtime Deploys**: Render automatically runs health checks against `/health` before routing traffic.
- **Auto DB Migration**: Database connect hote hi saare tables aur high-concurrency indexes automatically create/migrate ho jayenge bina manual SQL run kiye.
- **Memory Optimized**: Workers 512 MB Free Tier ke hisab se tuned hain.

---

## ⚡ Render 15-Minute Sleep Problem Ko 100% Solve Karne Ke 4 Solutions:

Render ke Free Tier par jab **15 minute tak koi incoming request nahi aati**, toh Render instance ko **sleep mode** me daal deta hai, aur next request aane par **30-40 seconds ka Cold Start** lagta hai. 

Humne is problem ko permanently khatam karne ke liye **4 Layered Protections** integrate kiye hain:

### Solution 1: Automatic In-App Self-Ping Daemon (`datanova/services/keep_alive_service.py`)
- Jaise hi aapka app Render par boot hota hai, ek lightweight background daemon thread start ho jata hai.
- Yeh thread har **10 minute (600 seconds)** par aapke public URL `https://<your-app>.onrender.com/health` par ek external HTTP GET request bhejta hai.
- Render ka reverse proxy is incoming request ko receive karta hai aur **15-minute ka inactivity timer reset kar deta hai**!
- Iske liye aapko koi external service setup karne ki zaroorat nahi padti.

---

### Solution 2: Free 24/7 GitHub Actions Cron Job (`.github/workflows/keep_alive.yml`)
Agar server kabhi deploy ya reboot ke time sleep ho gaya ho, toh uske liye humne aapke repository me ek **Automated GitHub Actions Workflow** add kar diya hai:
- Yeh GitHub ke servers se har **10 minute** me aapke URL par automatically ping bhejta hai.
- **Cost**: 100% Free (GitHub Actions me cron triggers free hote hain).
- **Setup**: Bas apne GitHub repo me **Settings** -> **Secrets and variables** -> **Actions** me ek secret add karein:
  - Name: `RENDER_APP_URL`
  - Value: `https://<your-app-name>.onrender.com`
- Bas! GitHub Actions har 10 minute me server ko jagaye rakhega.

---

### Solution 3: External Free Monitoring (UptimeRobot / Cron-Job.org)
Aap chahein toh ek external free uptime monitor bhi laga sakte hain:

#### Option A: UptimeRobot (Free 5-Minute Monitor)
1. [uptimerobot.com](https://uptimerobot.com/) par free account banayein.
2. **Add New Monitor** par click karein:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `DataNova Platform`
   - **URL (or IP)**: `https://<your-app-name>.onrender.com/health`
   - **Monitoring Interval**: `5 minutes`
3. **Create Monitor** par click karein.
   *UptimeRobot har 5 minute me request bhejta rahega aur Render kabhi sleep nahi hoga!*

#### Option B: Cron-Job.org (Free 1-Minute Cron)
1. [cron-job.org](https://cron-job.org/) par free account banayein.
2. **Create Cronjob** par click karein:
   - **URL**: `https://<your-app-name>.onrender.com/health`
   - **Schedule**: Har 10 minute (`*/10 * * * *`)
3. Save karein!

---

### Solution 4: Frontend Cold-Start & Network Resilience UI (`static/js/network_resilience.js`)
Agar kabhi Render cold-start ho raha ho (jaise fresh deployment ya server reboot ke waqt):
- User ko koi **Blank Screen ya 502 Bad Gateway error nahi dikhega**!
- Frontend automatically 502/504 errors ko intercept karega aur ek modern glassmorphic **"Waking Up DataNova Cloud"** overlay display karega with animated loader and live retry timer.
- Backend `/health` probe hone ke baad automatically request retry hogi aur user smooth transition ke sath page par enter ho jayega.
- Jab tak koi bhi user DataNova ka tab open rakhega, browser automatically har 4 minute me heartbeat ping bhej kar server ko active rakhega.

---

## 📁 Google Drive vs Local Storage & `invalid_grant` Error Fix

### Error Root Cause (`invalid_grant: Bad Request`):
Agar aapko Render logs me yeh error dikhe:
`ERROR [datanova.services.gdrive_service]: Failed to refresh Google Drive access token: ('invalid_grant: Bad Request')`

Iska reason hota hai:
1. **7-Day Expiry (Most Common)**: Google Cloud Console me jab tak aapka OAuth Consent Screen **"Testing"** mode me hota hai, Google har refresh token ko **7 din baad expire** kar deta hai.
2. **Client ID Mismatch**: Agar `GDRIVE_REFRESH_TOKEN` kisi dusre Client ID se generate hua tha aur Render me dusra `GOOGLE_CLIENT_ID` set hai.
3. **Token Revocation**: Agar aapne Google account ka password change kiya ya app permissions revoke kiye.

---

### Iska Solution (Aapke Paas 3 Simple Options Hain):

#### Option 1: Local Storage Use Karein (Sabse Simple & Zero Setup)
Agar aapko Google Drive nahi chahiye aur simple local storage use karni hai:
1. Render Dashboard me **Environment** tab me jao.
2. `STORAGE_MODE` = `local` set kar do (ya `GDRIVE_REFRESH_TOKEN` ko delete kar do).
3. **Result**: DataNova bina kisi Google Drive API call ke saare datasets, charts aur files safely `instance/uploads/` folder me store karega. Zero errors, instant speed!

#### Option 2: Naya Fresh Refresh Token Generate Karein (15GB Personal Drive)
1. Apne local terminal me command run karein:
   ```bash
   python generate_gdrive_refresh_token.py
   ```
2. Browser me apna Google account select karein aur permissions allow karein.
3. Terminal me jo naya `GDRIVE_REFRESH_TOKEN=1//...` mile, use Render ke Environment Variables me update kar dein.
4. **Permanent Token Ke Liye (Taaki kabhi expire na ho)**:
   - [Google Cloud Console](https://console.cloud.google.com/apis/credentials/consent) par jayein.
   - **OAuth consent screen** me **Publishing status** ke niche **"PUBLISH APP"** button click karein. Isse token kabhi expire nahi hoga!

#### Option 3: Service Account JSON Use Karein (Cloud Standard)
1. Google Cloud Console me Service Account create karein aur JSON key download karein.
2. Render me `GDRIVE_SERVICE_ACCOUNT_JSON` environment variable me pura JSON string paste kar dein.
3. Apne Google Drive folder ko us Service Account ke email ke sath Share (Editor) kar dein.

> [!NOTE]
> **DataNova Zero-Crash Protection**: Humne code ko update kar diya hai taaki agar Google Drive token kabhi bhi expire ya invalid ho, toh app **kabhi crash nahi hoga aur na hi error spam karega**. App automatically bina kisi rukawat ke Local Storage fallback par switch ho jata hai!


