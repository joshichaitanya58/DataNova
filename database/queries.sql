CREATE DATABASE IF NOT EXISTS DATANOVA;
USE DATANOVA;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'viewer',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS datasets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    file_size BIGINT, -- Storing size in bytes
    file_type VARCHAR(10), -- 'csv', 'xlsx'
    row_count INT,
    column_count INT,
    missing_values_count INT DEFAULT 0,
    duplicate_rows_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'uploaded', -- e.g., uploaded, processing, ready, error
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    eda_charts_json JSON,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
);

-- Create a new table to track API usage
CREATE TABLE IF NOT EXISTS api_usage_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'success' or 'failure'
    is_ai_call BOOLEAN DEFAULT FALSE,
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Shared Dashboards table for cross-role collaboration
CREATE TABLE IF NOT EXISTS shared_dashboards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,
    shared_with_role VARCHAR(20) DEFAULT NULL, -- 'all', 'viewer', 'manager', 'analyst'
    shared_with_user_id INT DEFAULT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    dataset_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE SET NULL
);

