# Building ZDE images

ZDE publishes `linux/amd64` and `linux/arm64` under the same version and `latest`
tags for both `zoul0813/zde-builder` and `zoul0813/zeal-dev-environment`.
Docker and Podman download only the variant matching their Linux VM or host.
Apple Silicon uses ARM64; Intel Macs and x86 Linux hosts use AMD64.

## Release workflow

Run from a checkout with Podman installed and its Linux VM running:

```sh
./build.sh 0.4.0
```

Replace the example version with the release version. Omitting it increments the
highest published semantic version's patch number. Authenticate with
`podman login docker.io` before choosing to publish.

The interactive script asks whether to rebuild the toolchain builder, confirms
the build, then asks before publishing. Rebuild the builder for the first
multi-architecture release: older builder tags contain only AMD64. Publish the
first dual-architecture images before distributing the updated host wrappers,
which now select the native platform.

Both architectures are built sequentially. On a single host, running build steps
for the other architecture requires working binfmt emulation (for example QEMU,
or the emulation supplied by the Podman VM). This is substantially slower than
native compilation. Building ARM64 on an ARM64 VM needs no x86 emulation.
SDCC and binutils use parallel Make builds on the available CPUs.

Builder builds retain SDCC 4.4.0 and binutils 2.41, and use a pinned upstream
multi-architecture z88dk `20260831` image. This version retains the library-build
interface needed by the existing Zeal target installer; newer upstream versions
require a separate integration update. The runtime stays on Alpine 3.24 to match
the builder's native library ABI. The existing target installation runs for
each architecture. Host tool executables differ, but all compilers and assemblers
still target the Zeal's Z80.

Local image tags have `-amd64` and `-arm64` suffixes. Version and `latest` tags
are manifest lists containing both variants. Newly rebuilt builders are always
used by the corresponding runtime build. When skipping the builder rebuild,
the script pulls each builder variant from the published `latest` manifest.

To reuse both local builders without pulling them:

```sh
USE_LOCAL_ZDE_BUILDER=true ./build.sh 0.4.0
```

Answer no to rebuilding the builder. The script requires
`zoul0813/zde-builder:latest-amd64` and `:latest-arm64`, and checks their platforms
before building either runtime image. Runtime base images such as Alpine can
still be downloaded if absent.

Declining publication leaves the images and manifests available locally. On
confirmation, `podman manifest push --all` publishes both image variants under
the version tag and `latest`. The architecture suffix tags are local build
references; they are not published as separate release tags. Registry updates
are sequential, so a failed push may leave earlier tags published; resolve the
error and rerun using the same version.

## Testing from a fresh worktree

The runtime image contains the toolchains; SDK checkouts and the Software
Collection catalog are initialized separately. From the ZDE checkout, use an
isolated state directory and initialize the catalog before installing aliases:

```sh
export ZDE_PATH="$PWD"
export CONTAINER_CMD=podman
export ZDE_IMAGE_REF=zoul0813/zeal-dev-environment:0.4.0
export ZDE_USER_PATH="$ZDE_PATH/tmp/image-test-state"
"$ZDE_PATH/zde" --no-tty sync
"$ZDE_PATH/zde" --no-tty deps install zos zvb zgdk coreutils
```

Use a local image reference before publication. From another project, invoke
`"$ZDE_PATH/zde" cmake build-image-test` to configure a fresh build directory.
An existing directory left by a failed CMake configuration must be reconfigured
or replaced before building; the wrapper only configures absent directories.

## CI validation

The existing unit-test workflow runs on native AMD64 and ARM64 Linux runners.
It pulls the pinned `0.4.0` image, runs the Python suite, and checks tool ELF
architectures plus real SDCC, z88dk, and GNU binutils compilation/linking.
Update the workflow image pin when preparing the next release. Publish and
validate the versioned images before pushing the release branch; promote
`latest` and push the Git release tag after both native CI jobs pass.

For this staged procedure, decline the script's publish prompt and publish each
versioned list with `podman manifest push --all <local-list> docker://<repo>:<version>`.
Keep separate local aliases for the lists while testing registry pulls, then
push those same lists to `latest` after CI passes. The script's normal publish
path updates version tags and `latest` together.

## Validation before publication

Inspect both manifests and confirm they contain Linux AMD64 and ARM64:

```sh
podman manifest inspect docker.io/zoul0813/zde-builder:latest
podman manifest inspect docker.io/zoul0813/zeal-dev-environment:0.4.0
```

Run the standalone toolchain smoke test for each local image (replace `arm64`
with `amd64` for the other variant):

```sh
podman run --rm --platform linux/arm64 --entrypoint /bin/sh \
  -v "$PWD/build/smoke.sh:/tmp/zde-smoke.sh:ro" \
  docker.io/zoul0813/zeal-dev-environment:0.4.0-arm64 /tmp/zde-smoke.sh
```

On each architecture, use the local versioned runtime variant to run the suite:

```sh
ZDE_USE=podman ZDE_IMAGE_REF=docker.io/zoul0813/zeal-dev-environment:0.4.0-arm64 ./zde --no-tty test
```

Use `-amd64` for AMD64 validation. Also compile representative SDCC, z88dk,
and GNU assembler projects, and check `zde emulator` and `zde playground` with
their dependencies installed. Validate on native machines when possible.

Compose and service launchers use the runtime's default architecture. Existing
`ZDE_IMAGE_REF`, `ZDE_IMAGE`, and `ZDE_VERSION` selection remains available.
Stop and restart existing emulator/playground services after pulling the new
image to replace their older containers.
Older single-architecture images on Apple Silicon may still require explicitly
selecting AMD64, for example `DOCKER_DEFAULT_PLATFORM=linux/amd64` with Docker.
