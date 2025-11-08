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

podman build -t zoul0813/zeal-dev-environment:$VERSION .
podman tag zoul0813/zeal-dev-environment:$VERSION docker.io/zoul0813/zeal-dev-environment:$VERSION
podman tag zoul0813/zeal-dev-environment:$VERSION docker.io/zoul0813/zeal-dev-environment:latest

read -p "Read pushings to register? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Pushing images..."
  podman push docker.io/zoul0813/zeal-dev-environment:$VERSION
  podman push docker.io/zoul0813/zeal-dev-environment:latest
else
  echo "Images built locally, but not pushed to register."
fi
