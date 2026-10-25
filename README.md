# 🚀 DataNova — Enterprise Data Science & Business Intelligence Platform

**DataNova** is a full-stack, role-based Data Science, Engineering, and Business Intelligence platform built with Python (Flask) and MySQL. It unifies data ingestion, automated preprocessing, exploratory data analysis (EDA), machine learning, SQL orchestration, and executive KPI reporting into a single collaborative ecosystem.

Designed around strict Role-Based Access Control (RBAC), DataNova provides specialized workspaces and toolsets tailored to four core organizational roles: **Administrators**, **Managers**, **Data Analysts**, and **Developers**.

---

## 👥 Role-Based Workspaces & Responsibilities

DataNova segments the data lifecycle across four dedicated workspaces, ensuring every team member has the exact tools required for their operational responsibilities:

### 🛡️ 1. Administrator (`Admin`)
**Focus:** *Platform Governance, Security, User Lifecycle & System Health*
* **User & Role Management:** Provision accounts, assign role-based permissions (`Admin`, `Manager`, `Analyst`, `Developer`), and manage user access states.
* **System Configuration:** Control global application parameters, feature flags, and environment configurations via `system_settings_service.py`.
* **Security & Audit Monitoring:** Track authentication logs, OTP verification statuses, and platform-wide activity to maintain compliance.
* **Storage & Cloud Oversight:** Manage Google Drive cloud synchronization settings and database connection health.

### 📊 2. Manager (`Manager`)
**Focus:** *Executive KPIs, Strategic Insights, Team Oversight & Reporting*
* **KPI Tracking & Dashboards:** Monitor real-time business metrics, performance indicators, and departmental targets (`kpi_service.py`).
* **Executive Reporting:** Generate, review, and export comprehensive PDF/HTML analytical reports for stakeholders (`report_service.py`).
* **AI-Driven Executive Summaries:** Leverage natural language insights and semantic summaries to make data-backed decisions without writing code (`insight_service.py`, `semantic_service.py`).
* **Project & Workflow Oversight:** Supervise analytical outputs, approve data models, and track team deliverables (`manager_service.py`).

### 🔬 3. Data Analyst (`Analyst`)
**Focus:** *Data Cleaning, Exploratory Data Analysis (EDA), Visualization & AutoML*
* **Automated Data Cleaning & Quality Scoring:** Detect and impute missing values, handle duplicates, encode categorical variables, and evaluate dataset health (`cleaning_service.py`, `quality_service.py`).
* **Outlier & Anomaly Detection:** Identify statistical anomalies using IQR and Z-Score methodologies (`outlier_service.py`).
* **Deep-Dive EDA & Interactive Charting:** Perform statistical profiling, correlation analysis, and generate dynamic visualizations (`eda_service.py`, `chart_service.py`).
* **Feature Engineering & AutoML:** Execute feature selection/scaling, train classification, regression, and clustering models, and evaluate model metrics directly in the browser (`feature_service.py`, `ml_service.py`).
* **Time-Series Forecasting:** Conduct trend decomposition, seasonality analysis, and future value forecasting (`timeseries_service.py`).

### 💻 4. Developer (`Developer`)
**Focus:** *Data Pipelines, SQL Orchestration, Database Engineering & Code Generation*
* **ETL & Data Pipeline Management:** Build, schedule, and monitor data ingestion and transformation pipelines (`pipeline_service.py`).
* **Live MySQL & `.sql` Dump Analysis:** Connect to external MySQL instances or parse uploaded `.sql` files for schema inspection, query profiling, and table diagnostics (`mysql_service.py`, `mysql_analysis_service.py`, `sql_file_service.py`).
* **Automated Code Export:** Translate browser-based data transformations and ML workflows into clean, reproducible Python and SQL scripts (`code_service.py`).
* **Big Data Optimization & APIs:** Optimize memory usage for large-scale datasets using chunking strategies and manage platform API integrations (`bigdata_optimizer.py`, `developer_service.py`).

---

## ✨ Core Platform Capabilities

* **🧠 AI Helper & Semantic Layer:** Conversational AI assistant for natural language data querying, automated statistical interpretation, and data dictionary mapping (`ai_helper.py`, `semantic_service.py`).
* **🔐 Enterprise Authentication:** Secure login and registration fortified with SMTP-based One-Time Password (OTP) verification and password recovery flows (`auth.py`, `otp_service.py`, `email_service.py`).
* **☁️ Google Drive Cloud Sync:** Seamless OAuth2 integration for automated dataset backups and cloud report storage (`gdrive_service.py`).
* **⚡ Offline & Network Resilience:** Progressive Web App (PWA) readiness with a custom Service Worker (`sw.js`) and client-side network recovery handling (`network_resilience.js`).

---

## 📂 Project Architecture

```text
DataNova/
├── api/
│   └── index.py                         # Serverless API entry point
├── database/
│   ├── db_connector.py                  # MySQL connection pooling & query execution
│   └── queries.sql                      # Relational schema & initial seed queries
├── datanova/
│   ├── __init__.py                      # Flask application factory & blueprint setup
│   ├── api.py                           # Core RESTful API routes
│   ├── auth.py                          # Authentication, RBAC & session management
│   ├── dashboards.py                    # Role-based workspace routing
│   └── services/                        # Modular Business Logic Layer
│       ├── admin_service.py             # Admin governance, user & role management
│       ├── ai_helper.py                 # LLM / AI assistant integration
│       ├── analyst_service.py           # Analyst workspace orchestration
│       ├── bigdata_optimizer.py         # Memory optimization & chunking engine
│       ├── chart_service.py             # Visualization payload builder
│       ├── cleaning_service.py          # Data imputation & preprocessing
│       ├── code_service.py              # Reproducible Python/SQL code generator
│       ├── developer_service.py         # Developer tools, logs & diagnostics
│       ├── eda_service.py               # Statistical profiling & EDA engine
│       ├── email_service.py             # Transactional SMTP email service
│       ├── feature_service.py           # Feature scaling, encoding & selection
│       ├── gdrive_service.py            # Google Drive API cloud storage sync
│       ├── insight_service.py           # Automated statistical pattern extraction
│       ├── keep_alive_service.py        # Background health-check worker
│       ├── kpi_service.py               # Executive KPI calculation engine
│       ├── manager_service.py           # Manager reporting & team oversight
│       ├── ml_service.py                # AutoML model training & evaluation
│       ├── mysql_analysis_service.py    # Live MySQL database profiler
│       ├── mysql_service.py             # External MySQL database connector
│       ├── otp_service.py               # OTP generation & verification
│       ├── outlier_service.py           # Statistical anomaly detection
│       ├── pipeline_service.py          # Data pipeline & ETL orchestration
│       ├── quality_service.py           # Dataset completeness & quality scoring
│       ├── report_service.py            # Automated PDF/HTML report compiler
│       ├── semantic_service.py          # Semantic data layer & business glossary
│       ├── sql_file_service.py          # .sql dump parser & schema analyzer
│       ├── system_settings_service.py   # Platform-wide configuration manager
│       └── timeseries_service.py        # Time-series decomposition & forecasting
├── static/
│   ├── assets/                          # Brand logos, favicons & visual assets
│   ├── css/                             # Modular stylesheets for auth & workspaces
│   ├── js/                              # Role-specific frontend controllers
│   │   ├── admin.js                     # Admin dashboard logic
│   │   ├── analyst.js                   # Analyst EDA & ML interface logic
│   │   ├── developer.js                 # Developer SQL & pipeline logic
│   │   ├── manager.js                   # Manager KPI & reporting logic
│   │   ├── common.js                    # Shared UI utilities & API handlers
│   │   └── network_resilience.js        # Connection monitoring & retry handling
│   └── sw.js                            # Service Worker for caching
├── templates/
│   ├── index.html                       # Platform landing page
│   ├── login.html                       # Role-aware authentication portal
│   ├── signup.html                      # Account registration
│   ├── forgot_password.html             # OTP password recovery flow
│   └── user/                            # Dedicated Role Dashboards
│       ├── admin_dashboard.html
│       ├── analyst_dashboard.html
│       ├── developer_dashboard.html
│       └── manager_dashboard.html
├── app.py                               # Application entry point
├── generate_gdrive_refresh_token.py     # CLI utility for Google OAuth2 setup
├── gunicorn.conf.py                     # Production WSGI server configuration
├── Procfile                             # Process declaration for cloud PaaS
├── render.yaml                          # Render Infrastructure-as-Code blueprint
├── requirements.txt                     # Python package dependencies
├── runtime.txt                          # Python runtime version (python-3.11.9)
├── DEPLOYMENT_GUIDE.md                  # General production deployment guide
└── RENDER_DEPLOYMENT_GUIDE.md           # Render-specific deployment instructions
```

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend Framework** | Python 3.11.9, Flask, Gunicorn (WSGI) |
| **Data Science & ML** | Pandas, NumPy, Scikit-Learn, SciPy |
| **Database** | MySQL (`mysql-connector-python`, `PyMySQL`) |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript (ES6+), Interactive Charting |
| **Cloud & Integrations** | Google Drive API (OAuth2), SMTP Email, Generative AI API |
| **DevOps & Hosting** | Render (`render.yaml`), Gunicorn (`Procfile`), Serverless (`api/index.py`) |

---

## ⚙️ Local Installation & Setup

### 1. Prerequisites
* **Python 3.11+**
* **MySQL Server** (Local instance or cloud-hosted MySQL)
* **Git**

### 2. Clone the Repository
```bash
git clone https://github.com/your-username/DataNova.git
cd DataNova
```

### 3. Set Up a Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Create a `.env` file in the project root directory:

```env
# Flask Core Settings
SECRET_KEY=your_production_secret_key
FLASK_ENV=development
PORT=5000

# MySQL Database Credentials
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=datanova_db

# SMTP Email & OTP Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_smtp_app_password
MAIL_DEFAULT_SENDER=your_email@gmail.com

# AI Assistant Integration (Optional)
GEMINI_API_KEY=your_ai_api_key

# Google Drive Cloud Sync (Optional)
GDRIVE_CLIENT_ID=your_google_client_id
GDRIVE_CLIENT_SECRET=your_google_client_secret
GDRIVE_REFRESH_TOKEN=your_google_refresh_token
```

> **Note:** To generate a `GDRIVE_REFRESH_TOKEN`, run `python generate_gdrive_refresh_token.py` and complete the OAuth2 browser prompt.

### 6. Initialize the MySQL Database
Execute the schema script located in `database/queries.sql` to create the required tables:
```bash
mysql -u root -p datanova_db < database/queries.sql
```

### 7. Start the Application
```bash
# Run in development mode
python app.py

# Run in production mode with Gunicorn
gunicorn app:app --config gunicorn.conf.py
```
Access the application at **`http://localhost:5000`**.

---

## ☁️ Production Deployment

DataNova includes pre-configured manifests for cloud deployment:

* **Render ( Blueprint Deployment):** Uses `render.yaml`, `Procfile`, and `gunicorn.conf.py` for automated builds. Refer to [RENDER_DEPLOYMENT_GUIDE.md](RENDER_DEPLOYMENT_GUIDE.md) for detailed instructions.
* **Custom VPS / Cloud Hosting:** Refer to [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for configuring reverse proxies, production MySQL instances, and background keep-alive services.

---

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/NewCapability`).
3. Commit your changes (`git commit -m 'Add NewCapability'`).
4. Push to the branch (`git push origin feature/NewCapability`).
5. Open a Pull Request.

---
