# ZDE code audit

Reviewed 2026-09-26 at commit `c5e406722419dbd3706fc345e7542ef77cc48855`.

19 findings: **2 P1, 16 P2, 1 P3**. Highest risks: deletion outside image staging and silent overwrite of existing project source. Existing unit suite passes; focused reproductions expose gaps outside its current assertions.

## Scope and method

Started at host `zde` entry point, followed container launch, Python dispatch, command handlers, shared modules, and TUI action paths. Reviewed ZDE-owned services, activation, dependency catalog/update/migration logic, configuration, image/kernel orchestration, project templates, container/build definitions, GitHub setup action, and tests. Checked documentation against implemented behavior.

Excluded installed dependency repositories under `home/` and `home/extras/`; excluded downloaded toolchain sources under `build/z88dk/`. ZDE-owned `home/zde/`, `home/templates/`, `home/.bashrc`, and `home/zde/deps.yml` remain in scope. Bundled `xdg-*` helpers reviewed only at ZDE integration boundary, not as an upstream desktop-utilities audit.

Validation used temporary directories, synthetic Git repositories, real Cookiecutter rendering, a stub container runtime, and mocked external image/build commands. No installed dependency repository was inspected or changed. No actual compiler, CMake, FUSE mount, container image build, or live GitHub workflow executed. Production code unchanged; findings recorded here only.

Severity: P1 = data-loss risk needing early correction; P2 = functional failure or incorrect success/state; P3 = narrower usability/test-runner defect. These findings describe ZDE behavior, not vulnerabilities in excluded dependencies.

## Execution map

```text
zde
  -> home/zde/svcs/common.sh: initialization, runtime selection, mounts
  -> host handlers: activate, update, emulator, playground, exec, shell
  -> compose run -> entrypoint.sh -> UID/GID mapping -> /src
  -> home/zde/zde.py -> cmds.<command> -> mods.*
                                      -> TUI uses same command/domain layer

Dependency state: ~/.zeal8bit/{deps-lock.yml,collection.yml,deps.env,zde.conf.yml}
Dependency sources: ZDE home / extras
Project workspace: current host directory mounted at /src
Image staging/output: ZDE mnt directory mounted at /mnt
```

## Findings

### F01 — P1: ✅ Image deletion and staging can escape image root

**Locations:** [image.py](home/zde/mods/image.py#L146), lines 146–163; normalization/staging at lines 36–44 and 92–120; [file_tree.py](home/zde/mods/tui/panels/file_tree.py#L113), lines 113–123.

`Image.rm()` joins `self.root / raw` without containment checks. Absolute paths discard staging prefix; `..` traverses outside it. A command intended to remove staged files can therefore delete source files or entire writable directories in mounted `/src`, `/home/zeal8bit`, or another image. No extra confirmation exists on CLI path. TUI navigation also follows directory symlinks, allowing removal through a symlinked parent.

Staging has corresponding write escape: `_normalize_stage_root()` strips leading separators but preserves `..`; destination joins and existing symlinks remain unchecked.

**Reproduced:** temporary `tf` image removal of `../outside.txt` and an absolute temporary file deleted both and returned 0. Staging with root `../escaped` wrote outside `tf` directory.

**Fix:** centralize root-confined path resolution for reads, writes, navigation, and removal. Reject absolute removal paths, traversal, and root deletion; validate resolved destination/parent against image root. Define symlink behavior explicitly: unlink selected symlink rather than traverse its target. Regression cases must include symlinked parents and directory removal.

### F02 — P1: ✅ Project creation silently overwrites normalized destination

**Locations:** [create.py](home/zde/cmds/create.py#L131), lines 131–150; all bundled template directory names use `cookiecutter.name | lower | replace(' ', '-')`.

Overwrite guard checks `/src/<raw project name>`, but templates generate a different, normalized path. `--name 'My Project'` checks `/src/My Project`, then renders into `/src/my-project`. Unconditional Cookiecutter `-f` permits overwriting files there. Violates documented refusal to overwrite existing target directories.

**Reproduced:** fixture contained `my-project/src/main.c` with custom source. Called real creation handler with `My Project`, redirecting `/src` to temporary output. Real Cookiecutter replaced custom source; handler returned 0.

**Fix:** remove unconditional `-f`; let Cookiecutter reject existing rendered destination. For arbitrary external templates, raw-name normalization alone cannot reliably predict destination. Test names differing by case/space and templates with custom output-directory expressions.

### F03 — P2: ✅ Failed image replacement destroys previous working image

**Locations:** [image.py](home/zde/mods/image.py#L225), lines 225–236 and 313–323.

CF and ZealFS image creation unlink existing output immediately after overwrite confirmation, before replacement succeeds. Invalid size, unavailable mount support, full disk, or tool failure can leave no usable image. Overwrite approval becomes loss of previous image even when operation reports failure.

**Reproduced:** existing TF image contained known-good bytes; confirmed overwrite; mocked image builder returned 9 before writing. Handler returned 9 and previous image no longer existed.

**Fix:** build replacement beside destination, complete copy/unmount/validation, then atomically replace destination. Preserve original on every failure path. Apply same publication discipline to ROM pack/concat outputs where feasible.

### F04 — P2: ✅ Strict exit mode cannot preserve Python command failures

**Locations:** [common.sh](home/zde/svcs/common.sh#L51), lines 51–55 and 87–94; [zde.py](home/zde/zde.py#L125), lines 125–129; [zde](zde#L9), lines 9–17 and 154–155.

Terminal detection sets `ZDE_SOFT_EXIT=1` regardless of `ZDE_STRICT_EXIT`. Container Python converts failure into success before host `finalize_exit()` can enforce strict mode. Thus `ZDE_STRICT_EXIT=1 zde config get bad-key` still returns 0 under terminal, allowing dependent shell commands to run after failure.

Opposite inconsistency: sourcing `common.sh` enables `set -e`; failed native/container commands can terminate wrapper before `finalize_exit()` runs. Soft-exit policy therefore differs between Python failures and `exec`/runtime failures.

**Reproduced:** real wrapper under pseudo-terminal with stub runtime: invalid config key plus strict mode returned 0; mocked failing `exec` returned 7 despite default soft mode.

**Fix:** preserve real statuses by default. If soft mode remains, derive it from one explicit policy, force it off under strict mode, and capture command statuses in conditional contexts where `errexit` cannot bypass finalization. Test host and Python failures under both TTY and pipe.

### F05 — P2: ✅ Image overrides do not consistently select execution image

**Locations:** [docker-compose.yml](docker-compose.yml#L6), line 6; [common.sh](home/zde/svcs/common.sh#L56), line 56; [setup action](github/setup-zde/action.yml#L64), lines 64–81.

Host wrapper calculates and exports `ZDE_IMAGE_REF`; services and update use it. Compose instead constructs image from `ZDE_IMAGE` and `ZDE_VERSION`. Setting only documented `ZDE_IMAGE_REF` changes reported/pulled/service image while Python commands still execute default image.

Setup action adds another mismatch: `image` input is used only for `docker pull`; never exported into ZDE selection variables. Subsequent `./zde update` and dependency installs can use/pull default `latest`, regardless of selected input.

**Validation:** static data-flow trace. Example: only `ZDE_IMAGE_REF=example/zde:review` set leaves Compose expression at `zoul0813/zeal-dev-environment:latest`. No live runtime used.

**Fix:** use one resolved image reference across Compose, services, update, and version output. Export action's `image` input to same variable. Validate normal tags, registry ports, and digest references with Compose configuration tests.

### F06 — P2: ✅ Setup action discards pinned ZDE checkout

**Locations:** [setup action](github/setup-zde/action.yml#L54), lines 54–62 and 79–81; [host update](home/zde/svcs/update#L33), lines 33–44.

Action checks out requested `ref`, then invokes host `./zde update` merely to refresh catalog/dependencies. For tag/SHA checkout, HEAD is detached; updater switches to `main` and pulls latest. Explicit source pin therefore does not survive setup. Branch selections also advance beyond initially checked-out commit.

**Validation:** static trace from action checkout to detached-HEAD branch in update script. No live workflow executed.

**Fix:** split dependency/catalog maintenance from ZDE self-update. Setup should run maintenance without changing selected checkout or image. Regression workflow should assert requested SHA remains HEAD after setup.

### F07 — P2: ✅ Ordinary directories inside a Git checkout count as installed dependencies

**Locations:** [update.py](home/zde/mods/update.py#L44), lines 44–63; [deps.py](home/zde/mods/deps.py#L541), `refresh()` and installation checks at lines 605–628.

`is_git_repo()` checks `git rev-parse --is-inside-work-tree`. Git walks parent directories, so empty dependency directory beneath ZDE checkout qualifies despite having no repository of its own. Requirement checks report installed, environment exports point at unusable directory, and install takes update path. `update_repo()` then rejects missing local `.git`, preventing normal recovery by install.

**Reproduced:** created temporary outer Git repository with empty child directory. Child had no `.git`; ZDE returned `True` for installed-repository check.

**Fix:** require resolved Git worktree top-level to equal dependency path, while supporting proper `.git` files for linked worktrees/submodules. Test empty/non-Git children inside ZDE checkout with real Git, not only mocked return codes.

### F08 — P2: ✅ Partial update drops unrelated dependency lock entries

**Locations:** [deps.py](home/zde/mods/deps.py#L789), lines 789–800 and 846–859; analogous early writes at lines 815–816 and 875–876.

`sync_for_update()` loads lock, immediately replaces `dependencies` with empty map, then saves partial map on first failure. Dependencies not yet visited lose lock records although their files remain installed. Host service guards rely on lock membership, so unrelated emulator/playground services can become “missing”; dependency kernel selectors also lose their saved paths.

**Reproduced:** lock initially contained `a`, `b`, `c`; first sync returned 9. Persisted lock retained only `a`.

**Fix:** preserve prior entries while updating individual results. Prune only after complete successful scan, using explicit policy. Write lock atomically; add failure-at-first/middle/last tests proving untouched records survive.

### F09 — P2: ✅ Retrying failed dependency install marks it healthy without building

**Locations:** [deps.py](home/zde/mods/deps.py#L627), lines 627–638, 648–655; similar existing-checkout paths in `update_dep()` and `sync_for_update()`.

First install leaves repository present after build failure and records `build_failed`. Retry sees repository, syncs Git, writes `synced`, and skips build. Requirements and displayed state use repository presence, ignoring failed build. User can receive successful install while required binaries/libraries remain absent.

**Reproduced:** existing synthetic dependency with `build_failed` lock entry; Git update succeeded. `install_dep()` returned 0, changed status to `synced`, called build zero times.

**Fix:** distinguish fetched source from successful build. Retry failed/incomplete builds and preserve failure status until build succeeds. Requirements for built artifacts should account for readiness. Test fail-first-build → retry → successful artifact production.

### F10 — P2: ✅ Dependency branch changes fail after normal shallow clone

**Locations:** [update.py](home/zde/mods/update.py#L165), branch clone at lines 165–174; update at lines 197–203.

Branch update checks out requested branch before fetching it. ZDE's shallow branch clone normally knows only original branch. If catalog changes branch, neither local new branch nor `origin/<new>` exists; both checkout attempts fail and function returns before pull could fetch new branch.

**Reproduced:** temporary local origin had `main` and `next`; cloned `main` using ZDE-equivalent depth/branch options over `file://`. `update_repo(..., 'branch', 'next')` returned 128; checkout stayed on `main`.

**Fix:** fetch requested branch into explicit remote-tracking ref before checkout; preserve local edits/divergence protections. Test branch transition using real shallow repository.

### F11 — P2: ✅ Hidden dependency can invalidate entire visible catalog

**Locations:** [deps.py](home/zde/mods/deps.py#L502), lines 502–507; [catalog.py](home/zde/mods/catalog.py#L74), lines 74–83 and 288–296.

Catalog validates dependencies before filtering `zde: false` entries. Visible child may legally reference hidden parent during validation; filtering then removes parent, and topological traversal raises unhandled `KeyError`. One such catalog entry breaks dependency listing and TUI catalog loading. Since regular update loads current catalog before refreshing collection, normal update can also fail to repair cached bad graph.

**Reproduced:** catalog with hidden `parent` and visible `child` depending on it passed YAML loading, then `DepCatalog` raised `KeyError: 'parent'`.

**Fix:** separate presentation visibility from dependency graph membership, or reject/filter unsupported dependency chains with clear diagnostics. Validate merged/filtered graph before publishing collection; allow collection repair independently of old catalog loading.

### F12 — P2: ✅ ROM disk regeneration leaves default “latest” image stale

**Locations:** [image.py](home/zde/mods/image.py#L370), output selection around lines 370–376 and publication at 416–425; [kernel.py](home/zde/mods/kernel.py#L394), versioned image and `latest.img` publication; [emulator service](home/zde/svcs/emulator#L25), default `r=latest` launch.

Kernel build publishes versioned ROM plus `mnt/roms/latest.img` symlink. Subsequent `zde image romdisk create` writes separate `mnt/roms/os_with_romdisk.img`, leaving versioned image and `latest.img` unchanged. Default emulator launch therefore still selects previous ROM after successful regeneration. Documentation explicitly promises latest-image update.

**Reproduced:** temporary `latest.img` pointed to old versioned bytes. Successful mocked pack/concat wrote new combined bytes to `os_with_romdisk.img`; `latest.img` still read old bytes.

**Fix:** define one ROM publication contract shared by kernel and romdisk commands. After successful regeneration, atomically publish/update default image reference. Align documentation and test default emulator target after regeneration. Also select configuration consistently with kernel build artifact; dependency internals not reviewed here.

### F13 — P2: ✅ CF image size argument is accepted but discarded

**Locations:** [image.py](home/zde/mods/image.py#L231), lines 231–244; CF handler registration at line 431.

`ImagePack.create()` accepts and prints requested size, then `_pack()` receives output/input paths only. Size never affects invocation or post-processing. Thus documented CF size control has no effect; invalid values also pass through without validation.

**Reproduced:** CF creation with `64` and `128` generated identical tool calls.

**Fix:** implement validated sizing appropriate to packed CF format, or remove unsupported argument/default from CLI, TUI, and documentation. Verify actual output sizing in integration test once external format/tool contract is established.

### F14 — P2: ✅ Failed filesystem copy skips unmount

**Locations:** [image.py](home/zde/mods/image.py#L282), lines 282–300.

After successful ZealFS mount, nonzero `rsync` result returns immediately. Shared `/media/zealfs` remains mounted. Especially in persistent TUI or interactive container, next image operation encounters stale mount; partially written image remains attached.

**Reproduced:** mount command returned 0, copy returned 23. `_build_image()` returned 23 without invoking `umount`.

**Fix:** once mount succeeds, unmount in `finally`; preserve primary copy failure while also reporting cleanup failure. Use distinct mount directory per operation and publish output only after clean unmount. Test copy exception, nonzero copy result, interruption, and unmount failure.

### F15 — P2: Service containers omit host identity used by normal commands

**Locations:** [common.sh](home/zde/svcs/common.sh#L176), lines 176–182; [playground](home/zde/svcs/playground#L16), lines 16–23; [entrypoint.sh](entrypoint.sh#L7), lines 7–8 and 36.

Normal Compose execution passes `HOST_UID/HOST_GID`; direct service launch and playground manifest builder do not. Entrypoint defaults to 1000:1000 and changes mounted home-directory ownership. On Linux hosts with different UID, playground files installed under actual UID are commonly unwritable by manifest builder; startup fails before serving. Ownership behavior also differs from regular ZDE commands.

**Validation:** static argument/environment trace. Runtime-specific mount ownership behavior not exercised; failure condition is native bind mount with host-owned files not writable by UID 1000.

**Fix:** share container identity argument construction across Compose and direct runs. Pass host IDs to both service startup and manifest builder; test non-1000 host UID and ensure ownership remains correct.

### F16 — P2: Asset preprocessing failure is ignored by `zde make`

**Locations:** [make.py](home/zde/cmds/make.py#L10), lines 10–13.

When `ASEPRITE_PATH` exists, wrapper runs asset Makefile but ignores return code. Main make can succeed using stale generated assets; overall command then reports success despite failed preprocessing.

**Reproduced:** mocked asset make returned 7, main make returned 0. Handler called both and returned 0.

**Fix:** stop immediately on preprocessing failure and propagate status. Add regression asserting main build is not invoked after asset step fails.

### F17 — P2: Existing empty/failed build directory prevents CMake configuration

**Locations:** [cmake.py](home/zde/cmds/cmake.py#L15), lines 15–23.

Wrapper equates directory existence with configured build tree. Pre-created `build/`, or directory left behind by failed initial configuration, skips configure and proceeds directly to build. Re-running `zde cmake` cannot repair this state; user must discover need to remove/fix directory manually.

**Validation:** static branch trace. No CMake process executed during audit.

**Fix:** validate generated build configuration rather than directory alone, or configure before each build. Regression: create empty `build/`, invoke exactly `zde cmake`, require successful configure/build; also test retry after failed configuration.

### F18 — P2: Unknown commands return success

**Locations:** [zde.py](home/zde/zde.py#L93), lines 93–96; related fallback in [config.py](home/zde/cmds/config.py#L143) and [image.py](home/zde/cmds/image.py#L24).

Unknown top-level command prints error then returns `print_top_help()` result, which is 0. Some invalid subcommands similarly return successful help. Scripts containing typos silently continue without performing requested work, including noninteractive runs where soft-exit mode is disabled.

**Reproduced:** `main(['typo-command'])` returned 0. Existing router test explicitly accepts successful unknown-command fallback, so passing suite does not catch contract error.

**Fix:** print usage but return nonzero usage-error status for invalid commands/subcommands. Preserve 0 for explicit help/no-argument help. Test through host wrapper with piped output as well as direct router.

### F19 — P3: `zde test` depends on launching from ZDE repository root

**Locations:** [test.py](home/zde/cmds/test.py#L23), lines 23–34; [docker-compose.yml](docker-compose.yml#L17), workspace mount; [entrypoint.sh](entrypoint.sh#L5), working directory.

Test command hardcodes relative `home/zde/tests/...` paths. Normal wrapper mounts caller's project at `/src`; running `zde test` or TUI test action from generated project searches project-local test config, although actual ZDE tests remain available under `/home/zeal8bit/zde/tests`. Command fails to find configuration.

**Validation:** static working-directory/path trace. Repository-root unit run does not exercise this case.

**Fix:** derive suite/config/coverage paths from command module location; define how explicit user-supplied pytest paths resolve. Test from an unrelated temporary project directory.

## Validation results

| Check | Result |
| --- | --- |
| Existing ZDE Python unit suite | **223 passed**, 4.38 seconds |
| Python parse checks | **71 files passed** |
| Shell syntax checks | **9 ZDE-owned scripts passed** |
| Image removal/staging containment fixtures | Outside-root deletion and write reproduced |
| Real Cookiecutter overwrite fixture | Existing source replaced; return 0 |
| Failed image replacement fixture | Old image deleted; return 9 |
| Pseudo-terminal wrapper fixtures | Strict Python failure returned 0; native failure returned 7 |
| Real Git parent-directory fixture | Non-repository child classified installed |
| Partial-sync fixture | Three lock records reduced to one |
| Failed-build retry fixture | Zero build calls; status changed to `synced` |
| Real shallow Git branch-switch fixture | Return 128; branch unchanged |
| Filtered catalog fixture | Unhandled `KeyError` |
| ROM publication fixture | `latest.img` unchanged after successful regeneration |
| CF size fixture | Different sizes produced identical tool arguments |
| Failed filesystem-copy fixture | No unmount call after copy failure |
| Asset preprocessing fixture | Failure swallowed; return 0 |
| Unknown-command fixture | Return 0 |
| Headless TUI saved-theme smoke check | Saved `nord` theme preserved; no finding |

Existing suite invocation, with temporary user state/cache and bytecode disabled:

```sh
rtk proxy env PYTHONDONTWRITEBYTECODE=1 ZDE_USER_PATH=/tmp/zde-audit-state \
  uv run --offline --cache-dir /tmp/zde-audit-uv-cache --no-project \
  --with pytest --with pyyaml --with textual --with cookiecutter --with pillow \
  python -m pytest -c home/zde/tests/pytest.ini home/zde/tests \
  -o cache_dir=/tmp/zde-audit-pytest-cache
```

Test packages provisioned into temporary cache first. This command uses host Python, not published Linux image; it proves unit behavior only. Most existing tests mock Git/process/container boundaries. Focused Git, Cookiecutter, and wrapper fixtures specifically exercised boundaries missing from those mocks. Image-tool fixtures validate ZDE sequencing/arguments, not excluded tools' implementations.

## Recommended correction order

1. Contain image operations and stop implicit project overwrite: F01–F02.
2. Preserve previous artifacts and dependency state across failures: F03, F08–F09, F14.
3. Make runtime identity, exit status, source/image selection deterministic: F04–F06, F15, F18.
4. Repair dependency discovery/branch/graph behavior: F07, F10–F11.
5. Align produced artifacts and build/test command contracts: F12–F13, F16–F17, F19.

Add focused regression cases with each fix. Follow with Linux container integration for UID mapping, Compose image selection, FUSE cleanup, generated-project builds, and default emulator ROM selection. Those integrations remain unverified here because installed dependency code and live toolchain execution were outside audit scope.
