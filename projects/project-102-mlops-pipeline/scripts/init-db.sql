-- Create MLflow database and user
CREATE DATABASE mlflow;
CREATE USER mlflow WITH PASSWORD 'mlflow';
GRANT ALL PRIVILEGES ON DATABASE mlflow TO mlflow;

-- Connect to mlflow database and grant schema permissions
\c mlflow;
GRANT ALL ON SCHEMA public TO mlflow;
