#!/bin/bash

echo "⚙️  Injecting LLM Environment Variables..."
export LLM_DRY_RUN=false
export LLM_WARMUP_ON_START=true
export LLM_EFFECTIVE_MAX_TOKENS=1024
export LLM_CACHE_ENABLED=true
export LLM_CACHE_MAX_ENTRIES=1024

echo "🚀 Booting API... (Keyboard inputs are now disabled during warmup)"

# Use absolute python path and disconnect from standard input to prevent ghost interrupts
/Users/dinanath/Documents/hybrid-secret-scanner/backend/.venv/bin/python api_server.py --host 127.0.0.1 --port 8000 < /dev/null