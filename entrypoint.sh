#!/bin/bash
# Database auto-creates empty schema on first import of utils.database
# No pre-seeding — user uploads all data via Data Entry page
echo "Starting CityBCPAgent..."

exec streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
