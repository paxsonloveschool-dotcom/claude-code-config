#!/usr/bin/env python
"""
narrate.py — VoxCPM wrapper for content funnel narration.

Usage:
    python narrate.py "Your text here" output.wav
    python narrate.py --file script.txt output.wav
    python narrate.py "Text" output.wav --ref-audio sample.wav --ref-text "what sample says"

First run downloads VoxCPM2 weights (~4-8 GB) to ~/.cache/huggingface.
CPU inference on this hardware (AMD RX 580, no CUDA): ~10-20x realtime.
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="VoxCPM text-to-speech")
    parser.add_argument("text", nargs="?", help="Text to synthesize (or use --file)")
    parser.add_argument("output", help="Output WAV file path")
    parser.add_argument("--file", "-f", help="Read text from file instead of argument")
    parser.add_argument("--ref-audio", "-r", help="Reference audio for voice cloning")
    parser.add_argument("--ref-text", help="Transcript of reference audio (pair with --ref-audio)")
    parser.add_argument("--model", default="openbmb/VoxCPM2", help="HF model ID (default: VoxCPM2)")
    parser.add_argument("--no-denoiser", action="store_true", help="Skip denoiser load (saves RAM)")
    parser.add_argument("--no-optimize", action="store_true", help="Disable torch.compile (debugging)")
    parser.add_argument("--cfg", type=float, default=2.0, help="CFG guidance scale")
    parser.add_argument("--steps", type=int, default=10, help="Inference timesteps")
    args = parser.parse_args()

    # Get text
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8").strip()
    elif args.text:
        text = args.text
    else:
        print("ERROR: provide text as positional arg or --file", file=sys.stderr)
        sys.exit(1)

    if not text:
        print("ERROR: text is empty", file=sys.stderr)
        sys.exit(1)

    print(f"[narrate] Model: {args.model}")
    print(f"[narrate] Text: {len(text)} chars, ~{len(text.split())} words")
    print(f"[narrate] Output: {args.output}")
    print(f"[narrate] Loading model (first run downloads ~4-8 GB)...")

    from voxcpm import VoxCPM
    import soundfile as sf
    import numpy as np

    vc = VoxCPM.from_pretrained(
        hf_model_id=args.model,
        load_denoiser=not args.no_denoiser,
        optimize=not args.no_optimize,
    )
    print("[narrate] Model loaded.")

    # Build generate kwargs
    gen_kwargs = {
        "text": text,
        "cfg_value": args.cfg,
        "inference_timesteps": args.steps,
    }
    if args.ref_audio:
        if not Path(args.ref_audio).exists():
            print(f"ERROR: ref-audio not found: {args.ref_audio}", file=sys.stderr)
            sys.exit(1)
        gen_kwargs["reference_wav_path"] = args.ref_audio
        if args.ref_text:
            gen_kwargs["prompt_wav_path"] = args.ref_audio
            gen_kwargs["prompt_text"] = args.ref_text
        print(f"[narrate] Mode: voice cloning from {args.ref_audio}")
    else:
        print("[narrate] Mode: default synthesis (no reference audio)")

    print("[narrate] Synthesizing... (CPU inference, be patient)")
    wav = vc.generate(**gen_kwargs)

    if isinstance(wav, tuple):
        wav, sr = wav
    else:
        sr = 48000  # VoxCPM2 default

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), wav, sr)
    duration = len(wav) / sr
    print(f"[narrate] ✅ Saved {output_path} ({duration:.1f}s @ {sr}Hz)")


if __name__ == "__main__":
    main()
