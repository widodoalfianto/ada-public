@echo off
echo Starting Ada in DEVELOPMENT Mode (TEST_MODE=True)...

docker compose -p ada-dev --env-file .env.dev -f docker-compose.dev-full.yml up -d --build --force-recreate

echo.
echo Environment started!
echo - Alerts will be routed to TEST channels.
echo - Alerts will be prefixed with [TEST].
echo - Ports shifted: DB(5433), Redis(6380), Services(9001-9005)
echo.
