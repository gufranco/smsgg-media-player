from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smsggmedia import psgplay, target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Play a baked film's PSG writes through a model of the SN76489 into a WAV."
    )
    parser.add_argument("movie", type=Path, help="the baked stream, such as assets/movie.bin")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--target", choices=sorted(target.TARGETS), default=target.DEFAULT.name)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.movie.is_file():
        msg = f"no baked film at {args.movie}"
        raise SystemExit(msg)
    fields = psgplay.fields_of(args.movie.read_bytes())
    stereo = target.named(args.target).stereo
    psgplay.write_wav(args.out, psgplay.render(fields, stereo=stereo))
    print(f"{args.out}: {len(fields)} fields, {'stereo' if stereo else 'mono'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
