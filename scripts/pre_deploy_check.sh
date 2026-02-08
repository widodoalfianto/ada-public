#!/bin/bash
# scripts/pre_deploy_check.sh
# Verifies environment configuration before deployment.

ENV_TYPE=$1

if [ -z "$ENV_TYPE" ]; then
    echo "Usage: ./pre_deploy_check.sh [dev|prod]"
    exit 1
fi

echo "🔍 Running Pre-Deploy Checks for: $ENV_TYPE"

# Load .env file if it exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo "❌ Error: .env file not found!"
    exit 1
fi

if [ "$ENV_TYPE" == "prod" ]; then
    # PROD CHECKS
    # 1. TEST_MODE must be False
    if [ "$TEST_MODE" == "True" ]; then
        echo "❌ FAILURE: TEST_MODE is True in Production!"
        exit 1
    fi

    # 2. Database must be stock_db (checking connection string if available)
    # This is a loose check as .env might not have full standard string
    if [[ "$DATABASE_URL" != *"stock_db"* ]]; then
        echo "⚠️  WARNING: DATABASE_URL does not seem to point to 'stock_db'. Check configuration."
    fi

    echo "✅ Production Configuration seems VALID."

elif [ "$ENV_TYPE" == "dev" ]; then
    # DEV CHECKS
    # 1. TEST_MODE must be True (usually set in .env.dev, but checked here if merged)
    # Note: .env usually has TEST_MODE=False. Dev overrides are in .env.dev.
    # This script typically runs against .env. If checking Dev, we might need .env.dev.
    
    if [ -f .env.dev ]; then
        # Check source .env.dev for TEST_MODE
        DEV_TEST_MODE=$(grep "TEST_MODE" .env.dev | cut -d '=' -f2)
        if [ "$DEV_TEST_MODE" != "True" ]; then
            echo "❌ FAILURE: TEST_MODE is not True in .env.dev!"
            exit 1
        fi
    else
        echo "⚠️  WARNING: .env.dev not found."
    fi

    echo "✅ Dev Configuration seems VALID."

else
    echo "❌ Unknown environment type: $ENV_TYPE"
    exit 1
fi
