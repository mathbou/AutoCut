#
# Copyright (c) 2023 Mathieu Bouzard.
#
# This file is part of AutoCut 
# (see https://gitlab.com/mathbou/autocut).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
import argparse
from pathlib import Path
from tkinter import Tk, filedialog

from .auto_editor import main
from .constant import MARGIN, MIN_LENGTH, THRESHOLD


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--audio-file", "-a", type=Path, action='append')
    parser.add_argument("--min-length", "-ml", type=float, default=MIN_LENGTH)
    parser.add_argument("--margin", "-m", type=int, default=MARGIN)
    parser.add_argument("--threshold", "-t", type=int, default=THRESHOLD)

    args = parser.parse_args()

    main(args.input_path, args.min_length, args.margin, args.threshold, args.audio_file)


def gui():
    root = Tk()
    root.withdraw()

    video_types = [("Video Files", ".mp4 .mkv")]
    in_path = filedialog.askopenfilename(initialdir=Path.home(), filetypes=video_types)

    if not in_path:
        exit(0)
    else:
        in_path = Path(in_path)

    audio_types = [("Audio Files", ".mp3 .ogg .wav .flac .aac .m4a")]
    audio_paths = filedialog.askopenfilenames(initialdir="F:/obs", filetypes=audio_types)

    root.destroy()

    if audio_paths:
        audio_paths = [Path(audio_path) for audio_path in audio_paths]

    main(in_path, audio_files=audio_paths)
