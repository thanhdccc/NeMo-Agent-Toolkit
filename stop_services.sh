#!/bin/bash

# This script finds and kills all the server processes started by start_services.sh

echo "🛑 Stopping all services..."

# Use pkill with the -f flag to find processes by their full command string
pkill -f 'vllm serve "google/gemma-3-4b-it"'
pkill -f "aiq mcp --config_file examples/personal/src/personal/configs/config_mcp.yml"
#pkill -f "aiq serve --config_file=examples/personal/configs/config.yml"
pkill -f "npm run dev"

echo "✅ All services have been stopped."
