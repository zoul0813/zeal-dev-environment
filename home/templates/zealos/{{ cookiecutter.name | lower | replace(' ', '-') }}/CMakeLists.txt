cmake_minimum_required(VERSION 3.16)

# -------------------------------
# CMake Setup
# -------------------------------
# Application Version
set(APP_VERSION_MAJOR 0)
set(APP_VERSION_MINOR 1)
set(APP_VERSION_PATCH 1)
set(APP_NAME "{{ cookiecutter.name }}")
set(target_name "{{ cookiecutter.name | lower | replace(' ', '_') }}")

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/bin)

# Ensure the bin directory exists
file(MAKE_DIRECTORY ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})

# -------------------------------
# Toolchain
# -------------------------------
set(ZOS_TOOLCHAIN sdcc)
include($ENV{ZOS_PATH}/cmake/zos_init.cmake)

# -------------------------------
# Project
# -------------------------------
project(${target_name} C ASM)

# -------------------------------
# Executable
# -------------------------------
add_executable(${target_name}
  src/main.c
)

# -------------------------------
# Convert to binary
# -------------------------------
zos_add_outputs(${target_name})
