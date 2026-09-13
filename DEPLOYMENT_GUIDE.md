# 🚀 DataNova - Complete Vercel Production Deployment Guide

Yeh guide aapko DataNova platform ko **Vercel** par 100% production-ready deploy karne ke liye step-by-step process batati hai.

---

## 📋 Table of Contents
1. [Important Architecture Notice (Serverless & Cloud DB)](#1-important-architecture-notice)
2. [Step 1: Free Cloud MySQL Database Setup](#step-1-free-cloud-mysql-database-setup)
3. [Step 2: Initialize Database Tables](#step-2-initialize-database-tables)
4. [Step 3: Push Code to GitHub](#step-3-push-code-to-github)
5. [Step 4: Deploy on Vercel](#step-4-deploy-on-vercel)
6. [Step 5: Set Environment Variables in Vercel](#step-5-set-environment-variables-in-vercel)
7. [Step 6: Verify Live Deployment](#step-6-verify-live-deployment)
8. [Troubleshooting & FAQs](#troubleshooting--faqs)

---

## 1. Important Architecture Notice

> [!IMPORTANT]
> **Vercel Serverless Platform** par chalte samay:
> - Vercel cloud me chalta hai, isliye **Localhost MySQL (`localhost:3306`) Vercel se connect nahi ho sakta**. Aapko ek **Cloud MySQL Database** (jaise TiDB Cloud Serverless, Aiven, ya Railway) use karna hoga jo 100% Free hai.
> - Vercel ka filesystem read-only hota hai (except `/tmp`). Humne app me dynamic `/tmp` mapping configure kar di hai taaki file uploads aur session caching bina error ke smoothly chalein.

---

## Step 1: Free Cloud MySQL Database Setup

Aap niche diye gaye kisi bhi free cloud database provider par 2 minute me MySQL database create kar sakte hain:

### Option A: TiDB Cloud Serverless (Recommended - Free Tier Forever)
1. Go to [https://tidbcloud.com/](https://tidbcloud.com/) and Sign Up / Log In with GitHub or Google.
2. Click **Create Cluster** → Select **Serverless (Free Tier)**.
3. Cluster name dekar create karein.
4. Cluster dashboard me **Connect** button par click karein.
5. **General Connection String / Parameters** copy karein:
   - **Host**: `gateway01.xxx.prod.aws.tidbcloud.com`
   - **Port**: `4000`
   - **User**: `xxxx.root`
   - **Password**: `your_generated_password`
   - **Database**: `test` ya `datanova`

### Option B: Aiven MySQL (Free Cloud)
1. Go to [https://aiven.io/](https://aiven.io/)
2. Create a free MySQL service and copy Service URI & credentials.

---

## Step 2: Initialize Database Tables

Aap apne local machine se Cloud Database me DataNova ke tables initialize kar sakte hain:

1. Apni local `.env` file me temporarily Cloud Database ke credentials enter karein:
   ```ini
   DB_HOST=gateway01.xxx.prod.aws.tidbcloud.com
   DB_PORT=4000
   DB_USER=xxxx.root
   DB_PASSWORD=your_password_here
   DB_NAME=datanova
   DB_SSL=true
   ```
2. Terminal me test script run karein jo tables automatically create kar dega:
   ```bash
   python -c "from database.db_connector import init_db; print('Database Init:', init_db())"
   ```
3. Jab output `Database tables and high-concurrency indexes verified/created successfully.` aa jaye, toh database ready hai!

---

## Step 3: Push Code to GitHub

1. Ensure `.vercelignore` and `.gitignore` are present (local `.env` aur `venv/` commit nahi honge).
2. Git repository initialize aur commit karein:
   ```bash
   git init
   git add .
   git commit -m "feat: configure DataNova for Vercel production deployment"
   ```
3. GitHub par new repository banayein aur push karein:
   ```bash
   git remote add origin https://github.com/<your-username>/datanova.git
   git branch -M main
   git push -u origin main
   ```

---

## Step 4: Deploy on Vercel

1. Go to [https://vercel.com/](https://vercel.com/) and Log In with GitHub.
2. Click **"Add New..."** → **"Project"**.
3. Select your `datanova` GitHub repository and click **"Import"**.
4. **Framework Preset**: Leave as **Other** (Vercel will automatically detect `vercel.json` and `@vercel/python`).
5. **Root Directory**: `./` (default).

---

## Step 5: Set Environment Variables in Vercel

Deployment screen par **Environment Variables** section expand karein aur ye variables add karein:

| Variable Name | Example Value / Description |
|---|---|
| `DB_HOST` | `gateway01.xxx.prod.aws.tidbcloud.com` (Cloud Host) |
| `DB_PORT` | `4000` (or `3306`) |
| `DB_USER` | `xxxx.root` |
| `DB_PASSWORD` | `your_cloud_password` |
| `DB_NAME` | `datanova` |
| `DB_SSL` | `true` |
| `SECRET_KEY` | `64_character_random_hex_string` |
| `GROQ_API_KEY` | `gsk_xxxxxxxxxxxxxxxxxxxx` |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` |
| `FLASK_DEBUG` | `false` |

> **Generate SECRET_KEY**:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

6. Click **"Deploy"**!

---

## Step 6: Verify Live Deployment

1. Vercel build complete hote hi aapko production URL mil jayega (e.g., `https://datanova-xxx.vercel.app`).
2. Live URL open karein:
   - ✅ Check Login / Register page (`/login`, `/register`).
   - ✅ Register an account and login to Dashboard.
   - ✅ Upload a sample CSV/Excel file to verify data processing & charts.
   - ✅ Test AI Insights and Manager/Analyst dashboard views.

---

## 🛠️ Project Structure for Vercel

```
DataNova/
├── api/
│   └── index.py            # Vercel WSGI Serverless Entrypoint
├── datanova/               # Core Application Package
│   ├── __init__.py         # App factory with Serverless /tmp adaptation
│   ├── api.py              # API routes
│   ├── auth.py             # Auth routes & session management
│   ├── dashboards.py       # Dashboard routes
│   └── services/           # Analytics, AI, & Pipeline services
├── database/
│   └── db_connector.py     # Connection pool with SSL & auto-reconnect
├── static/                 # CSS, JS, Assets
├── templates/              # Jinja2 HTML templates
├── vercel.json             # Vercel Routing & Build Spec
├── .vercelignore           # Bundling Exclusions
├── requirements.txt        # Production dependencies
└── DEPLOYMENT_GUIDE.md     # This deployment guide
```

---

## Troubleshooting & FAQs

### Q1: `Internal Server Error (500)` on first page load
- **Reason**: Cloud MySQL connection credentials galat hain ya database unreachable hai.
- **Fix**: Vercel Dashboard → **Project Settings** → **Environment Variables** check karein. Make sure `DB_SSL=true` is set for cloud databases.

### Q2: Authentication fails with `caching_sha2_password`
- **Reason**: MySQL 8.0 default auth plugin requires `cryptography`.
- **Fix**: `requirements.txt` me `cryptography>=43.0.0` already add kar diya gaya hai.

### Q3: Vercel Function Timeout (504 Gateway Timeout) on heavy ML tasks
- **Reason**: Vercel Hobby tier has a default 10s timeout limit for serverless functions.
- **Fix**: DataNova has built-in optimizations (`bigdata_optimizer.py`) with chunking and sampling to keep response times under 2-3 seconds for large files.

---

🎉 **Your DataNova Analytics Platform is now 100% ready for Production Deployment on Vercel!**
