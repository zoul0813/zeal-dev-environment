#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

ARCHITECTURES=(amd64 arm64)
BUILDER_REPO=docker.io/zoul0813/zde-builder
ZDE_REPO=docker.io/zoul0813/zeal-dev-environment

check_builder() {
  local image=$1 arch=$2 actual
  if ! actual=$(podman image inspect "$image" --format '{{.Os}}/{{.Architecture}}'); then
    echo "Local builder image not found: $image" >&2
    exit 1
  fi
  if [ "$actual" != "linux/$arch" ]; then
    echo "Builder $image has platform $actual; expected linux/$arch" >&2
    exit 1
  fi
}

create_manifest() {
  local repo=$1 version=$2
  if podman manifest exists "$repo:$version"; then
    podman manifest rm "$repo:$version"
  elif podman image exists "$repo:$version"; then
    # Specify the tag explicitly; otherwise Podman untags every image alias.
    podman untag "$repo:$version" "$repo:$version"
  fi
  podman manifest create "$repo:$version" \
    "$repo:$version-amd64" "$repo:$version-arm64"
  if [ "$version" != latest ]; then
    podman tag "$repo:$version" "$repo:latest"
  fi
}

push_manifest() {
  local repo=$1 version=$2
  podman manifest push --all "$repo:$version" "docker://$repo:$version"
  podman manifest push --all "$repo:$version" "docker://$repo:latest"
}

get_latest_version() {
  local tags latest
  tags=$(podman search --format "{{.Tag}}" --list-tags "$ZDE_REPO") || return
  latest=$(printf '%s\n' "$tags" | awk '/^[0-9]+\.[0-9]+\.[0-9]+$/' | sort -V | tail -1)

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

if [ -n "${1:-}" ]; then
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
USE_LOCAL_ZDE_BUILDER=${USE_LOCAL_ZDE_BUILDER:-false}

if [ "$BUILD_BUILDER" = true ]; then
  if [ ! -f "$SDCC_TARBALL" ]; then
    echo "* Downloading SDCC $SDCC_VERSION source"
    mkdir -p build
    curl -fL "https://sourceforge.net/projects/sdcc/files/sdcc/$SDCC_VERSION/sdcc-src-$SDCC_VERSION.tar.bz2/download" -o "$SDCC_TARBALL"
  fi

  ./build/zeal8bit.sh fetch

  for arch in "${ARCHITECTURES[@]}"; do
    echo "* Building Builder for linux/$arch"
    podman build --platform "linux/$arch" -f Dockerfile.builder \
      -t "$BUILDER_REPO:$BUILDER_VERSION-$arch" .
  done
  create_manifest "$BUILDER_REPO" "$BUILDER_VERSION"
  for arch in "${ARCHITECTURES[@]}"; do
    podman tag "$BUILDER_REPO:$BUILDER_VERSION-$arch" "$BUILDER_REPO:latest-$arch"
  done

  read -p "Continue to build ZDE? (y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Build cancelled."
    exit 0
  fi
fi

# Resolve and validate BOTH builders before starting runtime builds. Newly built
# builders always win over the registry, independently of USE_LOCAL_ZDE_BUILDER.
for arch in "${ARCHITECTURES[@]}"; do
  if [ "$BUILD_BUILDER" != true ] && [ "$USE_LOCAL_ZDE_BUILDER" != true ]; then
    podman pull --platform "linux/$arch" "$BUILDER_REPO:latest"
    podman tag "$BUILDER_REPO:latest" "$BUILDER_REPO:latest-$arch"
  fi
  check_builder "$BUILDER_REPO:latest-$arch" "$arch"
done
if [ "$BUILD_BUILDER" != true ]; then
  create_manifest "$BUILDER_REPO" latest
fi

for arch in "${ARCHITECTURES[@]}"; do
  echo "* Building ZDE for linux/$arch"
  # Base images may be pulled if missing; the validated local builder must
  # remain local. Podman's default pull=missing provides both behaviors.
  podman build --platform "linux/$arch" --pull=missing \
    --build-arg "ZDE_BUILDER_IMAGE=$BUILDER_REPO:latest-$arch" \
    -t "$ZDE_REPO:$VERSION-$arch" .
done
create_manifest "$ZDE_REPO" "$VERSION"

read -p "Push to registry? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Images built locally, but not pushed to registry."
  exit 1
fi

if [ "$BUILD_BUILDER" = true ]; then
  echo "Pushing zde-builder:$BUILDER_VERSION"
  push_manifest "$BUILDER_REPO" "$BUILDER_VERSION"
fi

echo "Pushing ZDE manifests and both architecture images..."
push_manifest "$ZDE_REPO" "$VERSION"
