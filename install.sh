#!/bin/bash
### RTEC installation steps ###

set -eo pipefail

created_rtecv2=0
moved_src=0
moved_scripts=0
moved_pyproject=0
moved_uvlock=0

cleanup() {
	if [[ $moved_src -eq 1 && -d "RTECv2/src" ]]; then
		mv RTECv2/src .
	fi

	if [[ $moved_scripts -eq 1 && -d "RTECv2/scripts" ]]; then
		mv RTECv2/scripts execution\ scripts
	fi

	if [[ -f "RTECv2/__init__.py" ]]; then
		rm -f RTECv2/__init__.py
	fi

	if [[ $created_rtecv2 -eq 1 && -d "RTECv2" ]]; then
		rmdir RTECv2 2>/dev/null || true
	fi

	if [[ $moved_pyproject -eq 1 && -f "pyproject.toml.install.bak" ]]; then
		mv pyproject.toml.install.bak pyproject.toml
	fi

	if [[ $moved_uvlock -eq 1 && -f "uv.lock.install.bak" ]]; then
		mv uv.lock.install.bak uv.lock
	fi
}

trap cleanup EXIT

## Create RTECv2 package by changing the file structure *temporarily*.
if [[ -e "RTECv2" ]]; then
	echo "Error: RTECv2 already exists. Please remove or rename it and retry."
	exit 1
fi

mkdir RTECv2
created_rtecv2=1
touch RTECv2/__init__.py
mv src RTECv2
moved_src=1
mv execution\ scripts RTECv2/scripts
moved_scripts=1

## If local uv project metadata exists, hide it temporarily to avoid
## pyproject/setuptools conflicts with this legacy setup.py package.
if [[ -f "pyproject.toml" ]]; then
	mv pyproject.toml pyproject.toml.install.bak
	moved_pyproject=1
fi

if [[ -f "uv.lock" ]]; then
	mv uv.lock uv.lock.install.bak
	moved_uvlock=1
fi

## Install RTEC via uv (preferred) or pip.
machine="$(uname -s)"
if command -v uv >/dev/null 2>&1; then
	uv pip install .
elif [[ "$machine" == "Linux"* ]] || [[ "$machine" == "Darwin"* ]]; then
	pip3 install .
elif [[ "$machine" == "CYGWIN"* ]] || [[ "$machine" == "MINGW"* ]]; then
	py -m pip install .
else
	echo "Error: Unsupported OS '$machine'."
	exit 1
fi

## Add the user-base scripts path to PATH (best effort for current shell).
if [[ "$machine" == "Linux"* ]] || [[ "$machine" == "Darwin"* ]]; then
	NewPath=`python3 -m site --user-base`/bin
elif [[ "$machine" == "CYGWIN"* ]] || [[ "$machine" == "MINGW"* ]]; then
	NewPath=`py -m site --user-base`/bin
else
	NewPath=""
fi

if [[ -n "$NewPath" ]]; then
	case :$PATH: in
		*:$NewPath:*) ;;
		*) export PATH=$PATH:$NewPath ;;
	esac
fi
