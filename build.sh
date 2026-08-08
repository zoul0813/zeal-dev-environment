#!/bin/bash
set -e

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


read -p "Rebuild ZDE Builder? (y/N): " -n 1 -r
echo
BUILD_BUILDER=false
if [[ $REPLY =~ ^[Yy]$ ]]; then
  BUILD_BUILDER=true
  BUILDER_VERSION=$(date +%Y%m%d)
  echo "Builder version: $BUILDER_VERSION"
fi

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

SDCC_VERSION=4.4.0
SDCC_TARBALL=build/sdcc-src-$SDCC_VERSION.tar.bz2
ZDE_BUILDER_IMAGE=docker.io/zoul0813/zde-builder:latest
USE_LOCAL_ZDE_BUILDER=${USE_LOCAL_ZDE_BUILDER:-false}

if [ "$BUILD_BUILDER" = true ]; then
  if [ ! -f "$SDCC_TARBALL" ]; then
    echo "* Downloading SDCC $SDCC_VERSION source"
    mkdir -p build
    curl -L "https://sourceforge.net/projects/sdcc/files/sdcc/$SDCC_VERSION/sdcc-src-$SDCC_VERSION.tar.bz2/download" -o "$SDCC_TARBALL"
  fi

  ./build/zeal8bit.sh fetch

  echo "* Building Builder"
  podman build --platform linux/amd64 -f Dockerfile.builder -t docker.io/zoul0813/zde-builder:$BUILDER_VERSION .
  podman tag docker.io/zoul0813/zde-builder:$BUILDER_VERSION docker.io/zoul0813/zde-builder:latest

  read -p "Continue to build ZDE? (y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Build cancelled."
    exit 0
  fi
fi

echo "* Building ZDE"
ZDE_BUILD_ARGS=(
  --platform linux/amd64
  --build-arg "ZDE_BUILDER_IMAGE=$ZDE_BUILDER_IMAGE"
  -t "docker.io/zoul0813/zeal-dev-environment:$VERSION"
)

if [ "$USE_LOCAL_ZDE_BUILDER" = true ]; then
  if ! podman image exists "$ZDE_BUILDER_IMAGE"; then
    echo "Local builder image not found: $ZDE_BUILDER_IMAGE" >&2
    exit 1
  fi

  echo "* Using local builder: $ZDE_BUILDER_IMAGE"
  ZDE_BUILD_ARGS+=(--pull=never)
fi

podman build "${ZDE_BUILD_ARGS[@]}" .
podman tag docker.io/zoul0813/zeal-dev-environment:$VERSION docker.io/zoul0813/zeal-dev-environment:latest

read -p "Push to registry? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Images built locally, but not pushed to register."
  exit 1
fi

if [ "$BUILD_BUILDER" = true ]; then
  echo "Pushing zde-builder:$BUILDER_VERSION"
  podman push docker.io/zoul0813/zde-builder:$BUILDER_VERSION
  podman push docker.io/zoul0813/zde-builder:latest
fi

echo "Pushing images..."
podman push docker.io/zoul0813/zeal-dev-environment:$VERSION
podman push docker.io/zoul0813/zeal-dev-environment:latest
