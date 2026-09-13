-- ============================================================================
-- DataNova (Smart Analytics Platform) - Complete Database Schema & Queries
-- Compatible with MySQL 8.0+, MariaDB 10.5+, TiDB Cloud Serverless, Aiven, AWS RDS
-- ============================================================================

-- 1. Database Creation (Skip if using Cloud DB with predefined database name)
CREATE DATABASE IF NOT EXISTS datanova CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE datanova;

-- Disable foreign key checks during setup to ensure clean execution
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- 2. CORE APPLICATION TABLES DDL
-- ============================================================================

-- Table: Users
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'viewer', -- 'admin', 'manager', 'analyst', 'viewer'
    organization VARCHAR(100) NOT NULL DEFAULT 'General',
    phone VARCHAR(30) DEFAULT NULL,
    bio TEXT DEFAULT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- 'active', 'inactive', 'suspended'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_users_org_role (organization, role),
    INDEX idx_users_status (status),
    INDEX idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table: Datasets (Uploaded & Processed data files)
CREATE TABLE IF NOT EXISTS datasets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    file_size BIGINT, -- Size in bytes
    file_type VARCHAR(10), -- 'csv', 'xlsx', 'xls', 'json'
    row_count INT,
    column_count INT,
    missing_values_count INT DEFAULT 0,
    duplicate_rows_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'uploaded', -- 'uploaded', 'processing', 'ready', 'error'
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    eda_charts_json JSON,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_datasets_user_status (user_id, status),
    INDEX idx_datasets_uploaded (uploaded_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table: Reports (Generated HTML/PDF analytics reports)
CREATE TABLE IF NOT EXISTS reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    dataset_id INT NOT NULL,
    report_name VARCHAR(255) NOT NULL,
    report_type VARCHAR(50) DEFAULT 'HTML', -- 'HTML', 'PDF', 'EXCEL'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    INDEX idx_reports_user_dataset (user_id, dataset_id),
    INDEX idx_reports_created (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table: API Usage Logs (Audit logging & Rate telemetry)
CREATE TABLE IF NOT EXISTS api_usage_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'success', 'failure', 'error'
    is_ai_call BOOLEAN DEFAULT FALSE,
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_api_usage_user_called (user_id, called_at DESC),
    INDEX idx_api_usage_status (status, is_ai_call)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table: Shared Dashboards (Cross-role collaboration)
CREATE TABLE IF NOT EXISTS shared_dashboards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,
    shared_with_role VARCHAR(20) DEFAULT NULL, -- 'all', 'viewer', 'manager', 'analyst'
    shared_with_user_id INT DEFAULT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    dataset_id INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE SET NULL,
    INDEX idx_shared_owner (owner_id),
    INDEX idx_shared_role (shared_with_role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table: Manager Team Members (Hierarchy & Department Groups)
CREATE TABLE IF NOT EXISTS manager_team_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    manager_id INT NOT NULL,
    user_id INT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY manager_user_unique (manager_id, user_id),
    INDEX idx_team_manager (manager_id),
    INDEX idx_team_member (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table: Manager Tasks (Task assignment & tracking with dataset links)
CREATE TABLE IF NOT EXISTS manager_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    manager_id INT NOT NULL,
    assigned_to_id INT NOT NULL,
    task_title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(20) DEFAULT 'Medium', -- 'Low', 'Medium', 'High', 'Critical'
    status VARCHAR(20) DEFAULT 'Pending', -- 'Pending', 'In Progress', 'Completed', 'Blocked'
    due_date DATE DEFAULT NULL,
    remark TEXT,
    dataset_id INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE SET NULL,
    INDEX idx_tasks_mgr_assigned (manager_id, assigned_to_id, status),
    INDEX idx_tasks_due_status (due_date, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- 3. OPTIONAL SEED DATA (Default Administrator Account)
-- Default Password: AdminPassword@123 (Bcrypt Hash)
-- ============================================================================

INSERT INTO users (first_name, last_name, email, password, role, organization, phone, bio, status)
VALUES (
    'Admin',
    'DataNova',
    'admin@datanova.com',
    '$2b$12$e8wVfTzXvWf5hZzD1sKx2.G5g5T7nL8w1vF0sW3kP0x9b4x8e2y8q',
    'admin',
    'DataNova HQ',
    '+91 9876543210',
    'Platform Super Administrator',
    'active'
)
ON DUPLICATE KEY UPDATE first_name = VALUES(first_name);

-- ============================================================================
-- 4. USEFUL DIAGNOSTIC & VERIFICATION QUERIES
-- ============================================================================

-- Check all tables and row counts:
-- SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema = DATABASE();

-- View all registered users:
-- SELECT id, first_name, last_name, email, role, organization, status, created_at FROM users;

-- View latest datasets uploaded:
-- SELECT id, user_id, file_name, file_type, file_size, row_count, column_count, uploaded_at FROM datasets ORDER BY uploaded_at DESC LIMIT 10;

-- Check AI and API calls usage telemetry:
-- SELECT endpoint, status, is_ai_call, COUNT(*) as call_count FROM api_usage_logs GROUP BY endpoint, status, is_ai_call;
