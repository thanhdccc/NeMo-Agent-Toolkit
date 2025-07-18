#!/bin/bash

# This script starts all the necessary servers for the project in the background.

echo "🚀 Starting all services..."

# --- Start vLLM Server ---
echo "1/4: Starting vLLM server on port 8080..."
vllm serve "google/gemma-3-4b-it" --port 8080 --max_model_len 32784 > vllm_server.log 2>&1 &
sleep 60 # Give it time to load the model

# --- Activate Environment & Start AIQ Servers ---
echo "2/4: Activating Python environment..."
cd ~/AIQToolkit || { echo "Error: Could not find ~/AIQToolkit. Exiting."; exit 1; }
source .venv/bin/activate || { echo "Error: Could not activate .venv. Exiting."; exit 1; }

echo "3/4: Starting AIQ MCP and Serve..."
aiq mcp --config_file examples/personal/src/personal/configs/config_mcp.yml > mcp_server.log 2>&1 &
sleep 10 # Wait for server to initialize

#aiq serve --config_file=examples/personal/configs/config.yml > aiq_server.log 2>&1 &
#sleep 10 # Wait for server to initialize

# --- Start Frontend UI Server ---
echo "4/4: Starting frontend UI server..."
cd ~/AIQToolkit/external/aiqtoolkit-opensource-ui/ || { echo "Error: Could not find UI directory. Exiting."; exit 1; }
npm run dev > ui_server.log 2>&1 &

echo "✅ All services have been launched in the background."
echo "   - Logs are saved to *.log files in their respective directories."
echo "   - To stop everything, run the 'stop_services.sh' script."
