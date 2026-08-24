# {{ cookiecutter.name }}

{{ cookiecutter.description }}

## Requirements

Make sure that you have [ZDE](https://github.com/zoul0813/zeal-dev-environment) installed.

Install the ZGDK dependency and its required libraries once:

```sh
zde deps install zgdk
```

## Build

From this project directory, run:

```sh
zde cmake
```

## Create Another Project

To create another ZGDK project from the same template, run:

```sh
zde create zgdk --name my-game
```
