# Admin User Guide

This guide explains how to manage the AI Gateway using the Administrator Dashboard.

## 1. Dashboard Overview

The **Dashboard** provides a real-time overview of the system status:

- **Total Requests**: Total number of API requests processed.
- **Active Models**: Number of models currently available.
- **Average Latency**: Average response time of LLM requests.
- **Error Rate**: Percentage of failed requests.
- **Usage Chart**: Visual representation of daily request volume.
- **Model Health**: Status indicators for each registered model endpoint.

## 2. User Management

Navigate to the **Users** menu to manage system users.

### 2.1 Managing Users
- **List Users**: View all registered users, their roles, and status.
- **Edit User**: Change user roles (Admin/User), reset passwords, or update email addresses.
- **Deactivate**: Disable user access without deleting the account.

### 2.2 API Keys
- Users can generate multiple API keys for different applications.
- Admins can view and revoke API keys for any user if necessary.

## 3. Organization Management

Navigate to the **Organizations** menu.

### 3.1 Setup
- **Create Organization**: Define new organizations for grouping users and models.
- **Organization Groups**: Create sub-groups within organizations (e.g., "Engineering", "Marketing") to assign specific model access permissions.

### 3.2 Join Requests
Navigate to **Join Requests** to handle membership applications:
- **Status**: View Pending, Approved, and Rejected requests.
- **Action**: Approve or Reject requests.
- **Details**: Click "Details" to view the user's reason for joining.

## 4. Provider & Model Management

### 4.1 Providers
Navigate to **Providers** to configure LLM backends:
- **Add Provider**: Register external services like OpenAI, Anthropic, or local services like Ollama/vLLM.
- **Type**: Select from supported types (openai, azure, anthropic, ollama, vllm, mock).
- **Base URL**: The API endpoint of the provider (e.g., `http://ollama:11434`).
- **Auth**: Configure API keys if required.

### 4.2 Models
Navigate to **Models** to define accessible models:
- **Alias**: The model name clients will use in API calls (e.g., `gpt-4`).
- **Display Name**: Human-readable name shown in UI.
- **Routing**: Map an Alias to one or more Provider Endpoints.
- **Load Balancing**: If multiple endpoints are assigned, requests are distributed.

## 5. Logs & Monitoring

Navigate to **Request Logs**:
- **Search**: Filter logs by Request ID, Model, User, or Status Code.
- **Details**: View full request payload, response, and latency.
- **Export**: Download logs as CSV for external analysis.

## 6. Security Features

### 6.1 PII Masking
If enabled, the system automatically detects and masks sensitive information (like emails, phone numbers) in prompt inputs and model outputs.

### 6.2 AI Security Scan (Garak)
Navigate to **Security Scan**:
- **Run Scan**: Initiate a vulnerability scan against a specific model.
- **Probe Types**: Select types of attacks to test (e.g., Injection, Jailbreak, Hallucination).
- **Reports**: View detailed pass/fail results for each probe.
