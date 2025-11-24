#!/bin/bash

get_latest_version() {
  latest=$(podman search --format "{{.Tag}}" --list-tags docker.io/zoul0813/zeal-dev-environment | grep -E "[0-9]+\.[0-9]+\.[0-9]+$" | sort -V | tail -1)

  if [ -z "$latest" ]; then
    echo "0.1.0"
  else
    echo "$latest"
  fi
}

increment_patch() {
    local version=$1
    local major=$(echo $version | cut -d. -f1)
    local minor=$(echo $version | cut -d. -f2)
    local patch=$(echo $version | cut -d. -f3)

    patch=$((patch + 1))
    echo "$major.$minor.$patch"
}

if [ -n "$1" ]; then
  VERSION=$1
else
  CURRENT_VERSION=$(get_latest_version)
  VERSION=$(increment_patch $CURRENT_VERSION)
  echo "Current version: $CURRENT_VERSION"
  echo "Building version: $VERSION"
fi

read -p "Continue with build? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Build cancelled."
  exit 1
fi

podman build --platform linux/amd64 -t docker.io/zoul0813/zeal-dev-environment:$VERSION .
podman tag docker.io/zoul0813/zeal-dev-environment:$VERSION docker.io/zoul0813/zeal-dev-environment:latest

read -p "Push to registry? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Images built locally, but not pushed to register."
  exit 1
fi

echo "Pushing images..."
podman push docker.io/zoul0813/zeal-dev-environment:$VERSION
podman push docker.io/zoul0813/zeal-dev-environment:latest

