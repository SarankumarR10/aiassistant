#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker was not found. Install Docker Engine/Desktop, then run this script again." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but the engine is not running. Start Docker, then retry." >&2
    exit 1
fi

echo "Building the restricted runner image. The first build needs internet access to download its base image and compiler packages."
docker build -f docker/Dockerfile.runner -t edupilot-runner:latest docker
echo "EduPilot code runner is ready. Restart EduPilot and open Local Code Runner."
