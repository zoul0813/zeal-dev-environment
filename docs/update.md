# `zde update`

`update` is a host-managed command that also runs ZDE maintenance steps.

## Usage

```sh
zde update
```

## Host-Side Behavior

- Determines the target branch.
- Uses `ZDE_BRANCH` if it is set.
- Otherwise stays on the current branch when it is not `main`.
- Otherwise falls back to `main`.
- Fetches and fast-forward pulls that branch in the ZDE repository.
- Pulls the configured container image (`$ZDE_IMAGE_REF`).

## ZDE Maintenance Behavior

After the host update finishes, the wrapper runs the ZDE `update` command, which:

- runs legacy migration steps when needed
- synchronizes required dependencies
- refreshes dependency lock state

## Related Environment Variables

- `ZDE_BRANCH`: force the branch used for the repository update.
- `ZDE_IMAGE` and `ZDE_VERSION`: control the image reference.
- `ZDE_USE`: force `docker` or `podman`.

## Notes

- This is the first command to run after cloning the repository.
- The ZDE `update` module is not just a `git pull`; the host wrapper is what handles repository and image updates.
