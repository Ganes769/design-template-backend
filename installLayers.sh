#!/bin/bash

# Install Python deps into Lambda layer folders under ./layers
# Looks for files named *-requirements.txt and installs into <layer>/python/

set -euo pipefail

root_directory="./layers"

# Prefer manylinux arm64 wheels to match provider.architecture: arm64
install_requirements() {
    requirements_file="$1"
    directory=$(dirname "$requirements_file")
    pip3 install \
        --platform manylinux2014_aarch64 \
        --only-binary=:all: \
        --upgrade \
        --python-version 3.14 \
        --implementation cp \
        -t "$directory/python/" \
        -r "$requirements_file"
}

# Fallback for packages without manylinux arm64 wheels
install_requirements_normal() {
    requirements_file="$1"
    directory=$(dirname "$requirements_file")
    pip3 install -t "$directory/python/" -r "$requirements_file"
}

if [ ! -d "$root_directory" ]; then
    echo "No $root_directory directory found. Nothing to install."
    exit 0
fi

# Pass 1: binary-only manylinux installs
find "$root_directory" -type f -name '*-requirements.txt' -print | while read -r requirements_file; do
    directory=$(dirname "$requirements_file")
    relative_directory="${directory#"$root_directory"/}"

    if [ ! -d "$directory/python" ]; then
        echo "Installing requirements (manylinux aarch64) for $requirements_file..."
        install_requirements "$requirements_file" || true
    else
        echo "Python directory already exists in $relative_directory. Skipping installation."
    fi
done

# Pass 2: normal install for any layers that still have no python/ folder
find "$root_directory" -type f -name '*-requirements.txt' -print | while read -r requirements_file; do
    directory=$(dirname "$requirements_file")
    relative_directory="${directory#"$root_directory"/}"

    if [ ! -d "$directory/python" ]; then
        echo "Installing requirements (normal) for $requirements_file..."
        install_requirements_normal "$requirements_file"
    else
        echo "Python directory already exists in $relative_directory. Skipping installation."
    fi
done

echo "Done."
