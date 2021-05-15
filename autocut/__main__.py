import sys
import argparse
from pathlib import Path

sys.path.insert(0, Path(__file__).parents[1].as_posix())
__package__ = 'autocut'

from .auto_editor import main

parser = argparse.ArgumentParser()
parser.add_argument("input_path", type=Path)
parser.add_argument("--audio-file", "-a", type=Path, action='append')
parser.add_argument("--min-length", "-ml", type=float, default=1.75)
parser.add_argument("--margin", "-m", type=int, default=4)
parser.add_argument("--threshold", "-t", type=int, default=-50)

args = parser.parse_args()

main(args.input_path, args.min_length, args.margin, args.threshold, args.audio_file)
