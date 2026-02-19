# Deploying Job Processor as a Service (Ubuntu)

This guide explains how to set up the Job Processor as a background service on a headless Ubuntu server using a Python virtual environment (`venv`) and `systemd`.

## 1. Prerequisites

- Ubuntu Server (Headless)
- Python 3.10+ installed
- MongoDB access (local or remote)
- Ollama or OpenAI API keys (as configured)

## 2. Setup Environment

Clone your project to the server and navigate to the root directory (the parent of `job_processor`):

```bash
cd /path/to/python_exp
```

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## 2.1 Manual Execution

If you want to run the processor manually (not as a service), ensure you are in the parent directory of `job_processor` and run:

```bash
python3 -m job_processor.main
```

> [!NOTE]
> Running as a module (`-m`) is required for the internal imports to work correctly.

## 3. Configuration

Ensure your `config.py` has the correct settings or set them via environment variables. You can create a `.env` file if your application supports it, or define them in the service file.

Key variables to check:
- `MONGO_URI`: Current database address (e.g., `mongodb://localhost:27017/careerforge`)
- `LLM_EXTRACTION_PROVIDER`: `ollama` or `openai`
- `OPENAI_API_KEY`: Required if using OpenAI

## 4. Create systemd Service

Create a service unit file:

```bash
sudo nano /etc/systemd/system/job-processor.service
```

Paste the following configuration. 

> [!IMPORTANT]
> You **MUST** replace `<your-username>`, `<your-group>`, and `/path/to/job_processor` with the actual values for your server.
> - To find your username: `whoami`
> - To find your group: `groups` (usually the same as your username)
> - To find your project path: `pwd` while inside the project directory.

```ini
[Unit]
Description=Job Processor Change Stream Listener
After=network.target mongodb.service

[Service]
# IMPORTANT: Replace with your actual username and group
User=<your-username>
Group=<your-group>
# IMPORTANT: Replace /path/to/python_exp with the parent folder of job_processor
WorkingDirectory=/path/to/python_exp
# IMPORTANT: Replace with the actual path to your venv and use -m to run as a module
ExecStart=/path/to/python_exp/venv/bin/python3 -m job_processor.main
Restart=always
RestartSec=10

# Environment variables can be defined here
# Environment=MONGO_URI=mongodb://localhost:27017/careerforge
# Environment=LLM_EXTRACTION_PROVIDER=ollama

[Install]
WantedBy=multi-user.target
```

## 5. Enable and Start Service

Reload systemd to recognize the new service:

```bash
sudo systemctl daemon-reload
```

Enable the service to start on boot:

```bash
sudo systemctl enable job-processor
```

Start the service:

```bash
sudo systemctl start job-processor
```

## 6. Monitoring

Check the status of the service:

```bash
sudo systemctl status job-processor
```

View real-time logs:

```bash
journalctl -u job-processor -f
```
