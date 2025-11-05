module.exports = {
  apps : [{
    name      : 'fastapi-service',
    // Path to your Conda Python interpreter
    interpreter : '/home/asadullahbeg/miniconda3/bin/python', 
    // The script should be the Python module flag: -m
    script    : '-m', 
    // Pass the ENTIRE uvicorn command as one single string in 'args'
    args      : 'uvicorn app.main:app --port 8000 --timeout-keep-alive 300 --timeout-graceful-shutdown 300',
    // ... other settings ...
  }]
};
