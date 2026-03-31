#!/bin/bash
if [ ! -f /app/db/bcp.db ]; then
    echo "First run — copying pre-seeded database..."
    if [ -f /app/db_seed/bcp.db ]; then
        cp /app/db_seed/bcp.db /app/db/bcp.db
        echo "Database ready."
    else
        echo "Seeding from Excel..."
        python3 seed_database.py
    fi
else
    echo "Database exists."
fi

exec streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
