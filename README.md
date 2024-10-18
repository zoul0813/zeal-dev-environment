# Zeal Development Environment

## Setup

Add the path of ZDE to your PATH

```shell
export ZDE_PATH="/path/to/ZDE"
export PATH="$PATH:$ZDE_PATH"
```

## Usage

```shell
zde update
zde start
zde make
zde stop
```

* `update` - pulls the latest ZDE updates, along with associated Zeal repos
* `start` - start ZDE, mounting the current directory as the project root (ie; /src)
* `stop` - stop ZDE
* `make` - execute make, passing all additional arguments (ie; `zde make all`)
