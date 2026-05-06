#!/usr/bin/env bash
set -euo pipefail

echo ""
echo " ========================================="
echo "  PDF Counsel (Docker)"
echo " ========================================="
echo ""

if ! command -v docker &>/dev/null; then
    echo " [error] Docker not found."
    echo " Install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    echo ""
    exit 1
fi

if ! docker info &>/dev/null 2>&1; then
    echo " [error] Docker is not running."
    echo " Please start Docker Desktop and try again."
    echo ""
    exit 1
fi

echo " Building and starting PDF Counsel..."
echo " (First run takes a few minutes while Docker builds the images)"
echo ""

docker compose up --build -d

echo ""
echo " ========================================="
echo "  PDF Counsel is running!"
echo ""
echo "  Open your browser at: http://localhost"
echo ""
echo "  To stop:      docker compose down"
echo "  To view logs: docker compose logs -f"
echo " ========================================="
echo ""

if command -v open &>/dev/null; then
    sleep 2 && open http://localhost
elif command -v xdg-open &>/dev/null; then
    sleep 2 && xdg-open http://localhost
fi
