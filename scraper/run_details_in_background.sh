#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

if [ -f crawl.pid ] && kill -0 "$(cat crawl.pid)" 2>/dev/null; then
    echo "Crawler is already running with PID $(cat crawl.pid)"
    exit 0
fi

nohup .venv/bin/python scraper/tgdd_scraper.py --mode details --only-listed >>crawl.log 2>&1 </dev/null &
echo $! > crawl.pid
echo "Started detail crawler with PID $(cat crawl.pid); log: crawl.log"
