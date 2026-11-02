import os

# Gunicorn configuration for KYK Technologies
# Enforces single-process multi-threading (1 worker, 50 threads) to guarantee
# in-memory Socket.IO session affinity on Render without requiring an external Redis queue.

bind = f"0.0.0.0:{os.environ.get('PORT', '3000')}"
workers = 1
threads = 50
worker_class = "gthread"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 10000
max_requests_jitter = 1000
accesslog = "-"
errorlog = "-"
loglevel = "info"
