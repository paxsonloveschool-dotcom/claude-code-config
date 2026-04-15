#!/bin/bash
# narrate.sh — quick VoxCPM wrapper for content funnel narration
# Usage:
#   ./narrate.sh "Text to speak" output.wav
#   ./narrate.sh --file script.txt output.wav
#   ./narrate.sh "Text" output.wav --voice "energetic young male narrator"
#
# Runs the narrate.py script inside the VoxCPM venv.

set -e

VOXCPM_DIR="$HOME/projects/VoxCPM"
VENV_PYTHON="$VOXCPM_DIR/.venv/Scripts/python.exe"

if [ ! -f "$VENV_PYTHON" ]; then
  echo "ERROR: VoxCPM venv not found at $VOXCPM_DIR/.venv"
  echo "Run bootstrap: cd $VOXCPM_DIR && uv venv --python 3.11 && uv pip install voxcpm torch torchaudio --index-url https://download.pytorch.org/whl/cpu"
  exit 1
fi

cd "$VOXCPM_DIR"
"$VENV_PYTHON" narrate.py "$@"
