# VoxCPM Narration Tools

Wrapper scripts for [OpenBMB/VoxCPM](https://github.com/OpenBMB/VoxCPM) — a 2B parameter TTS with voice cloning, 30-language support, and 48kHz output.

## Setup (one-time per device)

```bash
# 1. Clone VoxCPM
cd ~/projects
git clone https://github.com/OpenBMB/VoxCPM
cd VoxCPM

# 2. Install uv (fast Python manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Create Python 3.11 venv (VoxCPM requires <3.13)
uv venv --python 3.11

# 4. Install PyTorch CPU + VoxCPM
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
uv pip install voxcpm

# 5. Copy these scripts into the VoxCPM dir
cp ~/projects/claude-code-config/tools/voxcpm/narrate.py ~/projects/VoxCPM/
cp ~/projects/claude-code-config/tools/voxcpm/narrate.sh ~/projects/VoxCPM/
chmod +x ~/projects/VoxCPM/narrate.sh
```

## Usage

```bash
cd ~/projects/VoxCPM

# Basic synthesis
./narrate.sh "Your text here" output.wav

# Read from file
./narrate.sh --file script.txt output.wav

# Voice cloning from reference audio
./narrate.sh "Your text" output.wav \
  --ref-audio sample.wav \
  --ref-text "what the sample audio says"

# Save RAM on weak hardware
./narrate.sh "Text" output.wav --no-denoiser --no-optimize
```

## Performance notes

- **First run downloads ~4–8 GB of model weights** to `~/.cache/huggingface/`
- **CPU inference only** on machines without NVIDIA CUDA
- **On AMD Radeon RX 580 / Intel laptop CPUs:** expect ~10–20x realtime
  - 60 seconds of narration = 10–20 minutes of compute
  - Usable for batch pre-generation of content funnel voiceovers
  - Not usable for real-time generation
- **On NVIDIA RTX 4090:** ~0.3x realtime (real-time capable)

## Hardware alternatives if VoxCPM is too slow

| Tool | Speed | Cost | Quality |
|---|---|---|---|
| VoxCPM HF Spaces demo | Instant (cloud GPU) | Free tier | Excellent |
| Piper TTS | Faster than realtime | Free | Very good |
| OpenAI TTS API | Instant | ~$15/1M chars | Very good |
| ElevenLabs API | Instant | $5–22/mo | Best-in-class |

## Output format

- Sample rate: 48 kHz (VoxCPM2 default)
- Format: WAV (PCM float32)
- Mono
