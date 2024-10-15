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
import json
import re
import subprocess
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

import ffmpeg

from .constant import MARGIN, MAX_CACHE_SIZE, THRESHOLD


def probe(filename, cmd='ffprobe', **kwargs):
    # type: (Path, str, Any) -> str
    """
    Run ffprobe on the specified file and return a JSON representation of the output.

    Raises:
        ffmpeg.Error: if ffprobe returns a non-zero exit code
    """
    args = [cmd, '-of', 'json']
    args.extend(ffmpeg._utils.convert_kwargs_to_cmd_line_args(kwargs))
    args.append(filename.as_posix())

    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise RuntimeError('ffprobe', out, err)

    if args.count("-of") == 1:
        return json.loads(out.decode('utf-8'))
    else:
        return out.decode('utf-8').rstrip()


@lru_cache(MAX_CACHE_SIZE)
def framerate(path):
    # type: (Path) -> Fraction
    fps_ = probe(
        path, select_streams="v:0", show_entries="stream=r_frame_rate ", of="default=noprint_wrappers=1:nokey=1"
    )

    num, den = fps_.split("/")

    return Fraction(f"{num}/{den}")


@lru_cache(MAX_CACHE_SIZE)
def framelength(framerate):
    # type: (Fraction) -> float
    return framerate.denominator / framerate.numerator


@lru_cache(MAX_CACHE_SIZE)
def duration(path):
    # type: (Path) -> float
    """

    Returns: seconds
    """
    length = float(
        probe(path, select_streams="v:0", show_entries="format=duration ", of="default=noprint_wrappers=1:nokey=1")
    )

    return length


@lru_cache(MAX_CACHE_SIZE)
def resolution(path):
    # type: (Path) -> tuple[int, int]
    """

    Returns: width, height
    """
    width, height = probe(
        path,
        select_streams="v:0",
        show_entries="stream=coded_width:stream=coded_height",
        of="default=noprint_wrappers=1:nokey=1",
    ).splitlines()

    return int(width), int(height)


@lru_cache(MAX_CACHE_SIZE)
def audio_track_count(path):
    # type: (Path) -> int
    return len(
        probe(
            path, select_streams="a", show_entries="stream=index", of="default=noprint_wrappers=1:nokey=1"
        ).splitlines()
    )


def extract_audio(path):
    # type: (Path) -> list[Path]
    print("Extract Audio")
    count = audio_track_count(path)

    filepaths = list()

    for i in range(count):
        audio_codec = probe(
            path, select_streams=f"a:{i}", show_entries="stream=codec_name", of="default=noprint_wrappers=1:nokey=1"
        )

        out_path = Path(f"{path.parent}/{path.stem}-a{i}.{audio_codec}")

        ffmpeg.input(path.as_posix()).output(out_path.as_posix(), map=f"a:{i}", vn=None, acodec='copy').global_args(
            "-vn", "-sn", "-dn"
        ).run(overwrite_output=True)
        filepaths.append(out_path)

    print(f"{len(filepaths)} Audio tracks")
    return filepaths


def section_is_quiet(path, in_, out, threshold=THRESHOLD, frame_length=None):
    # type: (Path, int, int, float, Fraction) -> bool
    abs_in = float(in_ * frame_length)
    abs_out = float(out * frame_length)

    buf = ffmpeg.input(path.as_posix(), ss=round(abs_in, 2), to=round(abs_out, 2))
    cmd = ffmpeg.filter(buf, 'volumedetect').output("-", format="null")
    lines = cmd.global_args("-vn", "-sn", "-dn").run(capture_stderr=True)[1]

    for line in lines.splitlines():
        max_volume = re.search(rb"max_volume: (-?[\d.]*) dB", line)

        if max_volume:
            max_volume = max_volume.groups()[0]
            return float(max_volume) < threshold

    return False


def get_silence_cuts(path, min_length=24, threshold=THRESHOLD, margin=MARGIN, audio_file=None):
    # type: (Path, float, float, int, Path) -> list[tuple[int, int]]
    """
    Cut the first audio track

    Args:
        path:
        min_length: frame
        threshold: Db
        margin: frame
        audio_file:

    Returns: list of frameranges
    """
    print("Get silence cuts")

    frame_length = framelength(framerate(path))

    if margin > min_length / 2.0:
        margin = int(min_length / 2.0)

    if audio_file:
        buf = ffmpeg.input(audio_file.as_posix())
    else:
        buf = ffmpeg.input(path.as_posix())

    cmd = ffmpeg.filter(buf, 'silencedetect', n="{}dB".format(threshold), d=min_length * frame_length).output(
        "-", format="null"
    )
    lines = cmd.global_args("-vn", "-sn", "-dn").run(capture_stderr=True)[1]

    silence_cuts = list()
    for line in lines.splitlines():
        start = re.search(rb"silence_start: ([-\d.]+)", line)
        end = re.search(rb"silence_end: ([-\d.]+)", line)

        if start:
            value = float(start.groups()[0])
            value = int(value / frame_length)
            value += margin

            value = max(0, value)
            silence_cuts.append([value])
        elif end:
            value = float(end.groups()[0])
            value = int(value / frame_length)
            value -= margin

            silence_cuts[-1].append(value)

    cuts = list()
    previous = -1

    for cut in silence_cuts:
        c_start = cut[0]
        c_end = cut[-1]

        if previous == c_start:
            cuts[-1][-1] = c_end
        else:
            cuts.append(tuple(cut))

        previous = c_end

    print(f"Silence cuts: {len(cuts)}")
    return cuts


def fill_sequence(path, silence_cuts, min_length=24.0):
    # type: (Path, list[tuple[int, int]], float) -> list[tuple[int, int, bool]]
    """

    Returns: list of frameranges and quiet status [start, end, is_quiet]
    """
    print("Fill sequences")

    duration_ = int(duration(path) / framelength(framerate(path)))

    # Compute cuts with sound
    cuts = list()
    for i, (start, end) in enumerate(silence_cuts):
        if start > 0 and i == 0:  # Test for gap before 1st cut
            cut_range = sorted([0, start])

            if sum(cut_range) > 0:
                cut_range.append(False)
                cuts.append(cut_range)

        try:
            start_2, end_2 = silence_cuts[i + 1]
        except IndexError:
            next_cut = [end_2, duration_]  # Last cut
        else:
            next_cut = [end, start_2]

        next_cut.sort()
        next_cut_start, next_cut_end = next_cut
        next_cut_duration = next_cut_end - next_cut_start

        current_cut = [start, end, True]
        cuts.append(current_cut)  # Add quiet cut

        if sum(next_cut) > 0 and next_cut[0] != next_cut[1]:
            if next_cut_duration <= min_length:
                next_cut.append(True)
            else:
                next_cut.append(False)

        cuts.append(next_cut)

    merged_cuts = []
    previous_status = None

    for i, (start, end, quiet) in enumerate(cuts):
        if i == 0:
            previous_status = quiet
            previous_start = start
            previous_end = end
            continue

        if previous_status == quiet:
            previous_end = end

        elif previous_status != quiet:
            merged_cut = (previous_start, previous_end, previous_status)
            merged_cuts.append(merged_cut)

            previous_status = quiet
            previous_start = start
            previous_end = end

    print(f"Total sequences: {len(cuts)} // Merged: {len(merged_cuts)}")
    return merged_cuts
