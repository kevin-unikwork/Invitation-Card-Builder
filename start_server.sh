#!/bin/bash
cd /home/kevin/Invitation_research

# Kill any existing server on port 8888
fuser -k 8888/tcp 2>/dev/null
sleep 1

# Start the server with LD_LIBRARY_PATH set for Playwright
source env/bin/activate
export LD_LIBRARY_PATH=/home/kevin/local_libs/extracted/usr/lib/x86_64-linux-gnu
python main.py
