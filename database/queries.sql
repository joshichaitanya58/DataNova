CREATE DATABASE IF NOT EXISTS DATANOVA;
USE DATANOVA;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'developer',
    organization VARCHAR(100) NOT NULL DEFAULT 'General',
    phone VARCHAR(30) DEFAULT NULL,
    bio TEXT DEFAULT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_users_org_role (organization, role),
    INDEX idx_users_status (status)
);

CREATE TABLE IF NOT EXISTS datasets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    file_size BIGINT, -- Storing size in bytes
    file_type VARCHAR(10), -- 'csv', 'xlsx'
    row_count BIGINT UNSIGNED,
    column_count INT UNSIGNED,
    missing_values_count BIGINT UNSIGNED DEFAULT 0,
    duplicate_rows_count BIGINT UNSIGNED DEFAULT 0,
    status VARCHAR(20) DEFAULT 'uploaded', -- e.g., uploaded, processing, ready, error
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    eda_charts_json JSON,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_datasets_user_status (user_id, status)
);

-- Create a new 'reports' table to track generated reports
CREATE TABLE IF NOT EXISTS reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    dataset_id INT NOT NULL,
    report_name VARCHAR(255) NOT NULL,
    report_type VARCHAR(50) DEFAULT 'HTML',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    INDEX idx_reports_user_dataset (user_id, dataset_id)
);

-- Create a new table to track API usage
CREATE TABLE IF NOT EXISTS api_usage_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'success' or 'failure'
    is_ai_call BOOLEAN DEFAULT FALSE,
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_api_usage_user_called (user_id, called_at)
);

-- Shared Dashboards table for cross-role collaboration
CREATE TABLE IF NOT EXISTS shared_dashboards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,
    shared_with_role VARCHAR(20) DEFAULT NULL, -- 'all', 'developer', 'manager', 'analyst'
    shared_with_user_id INT DEFAULT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    dataset_id INT,
    status VARCHAR(20) DEFAULT 'Shared',
    remark TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE SET NULL,
    INDEX idx_shared_owner (owner_id)
);

-- Manager Team Members Table
CREATE TABLE IF NOT EXISTS manager_team_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    manager_id INT NOT NULL,
    user_id INT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY manager_user_unique (manager_id, user_id),
    INDEX idx_team_manager (manager_id)
);

-- Manager Assigned Tasks with Dataset Attachment Support
CREATE TABLE IF NOT EXISTS manager_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    manager_id INT NOT NULL,
    assigned_to_id INT NOT NULL,
    task_title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(20) DEFAULT 'Medium',
    status VARCHAR(20) DEFAULT 'Pending',
    due_date DATE,
    remark TEXT,
    dataset_id INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE SET NULL,
    INDEX idx_tasks_mgr_assigned (manager_id, assigned_to_id, status)
);

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(20) DEFAULT 'info',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notifs_user (user_id, is_read)
);

-- Contact Admin / Support Messages Table
CREATE TABLE IF NOT EXISTS contact_admin_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    user_name VARCHAR(150) NOT NULL,
    user_email VARCHAR(150) NOT NULL,
    user_role VARCHAR(50) DEFAULT 'user',
    subject VARCHAR(255) NOT NULL,
    category VARCHAR(50) DEFAULT 'General Inquiry',
    message TEXT NOT NULL,
    attachment_url VARCHAR(500) DEFAULT NULL,
    status VARCHAR(20) DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_contact_user (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


