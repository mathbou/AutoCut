import re
import json
import ffmpeg
import subprocess

from fractions import Fraction
from pathlib import Path
from functools import lru_cache
from typing import NoReturn, Any, List

MAX_SIZE = 128


def probe(filename, cmd='ffprobe', **kwargs):
    # type: (Path, str, Any) -> NoReturn
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


@lru_cache(MAX_SIZE)
def framerate(path):
    """

    Args:
        path:

    Returns:
        Fraction:
    """
    fps_ = probe(path, select_streams="v:0", show_entries="stream=r_frame_rate ", of="default=noprint_wrappers=1:nokey=1")

    num, den = fps_.split("/")

    return Fraction(f"{den}/{num}")


@lru_cache(MAX_SIZE)
def duration(path):
    """

    Args:
        path (Path):

    Returns:
        float: seconds
    """
    length = float(probe(path, select_streams="v:0", show_entries="format=duration ", of="default=noprint_wrappers=1:nokey=1"))

    return length


@lru_cache(MAX_SIZE)
def resolution(path):
    """

    Args:
        path (Path):

    Returns:
        int, int: width, height
    """
    width, height = probe(path, select_streams="v:0", show_entries="stream=coded_width:stream=coded_height", of="default=noprint_wrappers=1:nokey=1").splitlines()

    return int(width), int(height)


@lru_cache(MAX_SIZE)
def audio_track_count(path):
    """

    Args:
        path (Path):

    Returns:
        int:
    """
    return len(probe(path, select_streams="a", show_entries="stream=index", of="default=noprint_wrappers=1:nokey=1").splitlines())


def extract_audio(path):
    # type: (Path) -> List[Path]
    count = audio_track_count(path)

    filepaths = list()

    for i in range(count):
        audio_codec = probe(path, select_streams=f"a:{i}", show_entries="stream=codec_name", of="default=noprint_wrappers=1:nokey=1")

        out_path = Path(f"{path.parent}/{path.stem}-a{i}.{audio_codec}")

        ffmpeg.input(path.as_posix()).output(out_path.as_posix(), map=f"a:{i}", vn=None, acodec='copy').run(overwrite_output=True)
        filepaths.append(out_path)

    return filepaths


def section_is_quiet(path, in_, out, threshold=-60, frame_length=None):
    """

    Args:
        path (Path):
        in_ (int):
        out (int):
        threshold (float):
        frame_length (Fraction):

    Returns:
        bool:
    """
    abs_in = float(in_ * frame_length)
    abs_out = float(out * frame_length)

    buf = ffmpeg.input(path.as_posix(), ss=round(abs_in, 2), to=round(abs_out, 2))
    cmd = ffmpeg.filter(buf, 'volumedetect').output("-", format="null")
    lines = cmd.run(capture_stderr=True)[1]

    for line in lines.splitlines():
        max_volume = re.search(b"max_volume: (-?[\d\.]*) dB", line)

        if max_volume:
            max_volume = max_volume.groups()[0]
            return float(max_volume) < threshold

    return False


def get_silence_cuts(path, min_length=24, threshold=-60, margin=7, audio_file=None):
    """
    Cut the first audio track

    Args:
        path (Path):
        min_length (float): frame
        threshold (float):
        margin (int): frame
        in_ (int): frame
        out (int): frame
        audio_file (Path):

    Returns:
        list(int, int): start, end
    """
    frame_length = float(framerate(path))

    if margin > min_length / 2.0:
        margin = int(min_length / 2.0)

    if audio_file:
        buf = ffmpeg.input(audio_file.as_posix())
    else:
        buf = ffmpeg.input(path.as_posix())

    cmd = ffmpeg.filter(buf, 'silencedetect', n="{}dB".format(threshold), d=min_length * frame_length).output("-", format="null")
    lines = cmd.run(capture_stderr=True)[1]

    silence_cuts = list()
    for line in lines.splitlines():
        start = re.search(b"silence_start: ([\-\d\.]+)", line)
        end = re.search(b"silence_end: ([-\\d\.]+)", line)

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
            cuts.append(cut)

        previous = c_end

    return cuts


def fill_sequence(path, silence_cuts):
    """

    Args:
        path (Path):
        silence_cuts (list):

    Returns:
        list(int, int, is_quiet): start, end, is_quiet
    """
    duration_ = int(duration(path) / float(framerate(path)))

    # Compute cuts with sound
    cuts = list()
    for i, (start, end) in enumerate(silence_cuts):
        if start > 0 and i == 0: # Test for gap before 1st cut
            cut_range = sorted([0, start])

            if sum(cut_range) > 0:
                cut_range.append(False)
                cuts.append(cut_range)

        cuts.append([start, end, True])

        try:
            start_2, end_2 = silence_cuts[i+1]
        except IndexError:
            next_cut = [end_2, duration_] # Last cut
        else:
            next_cut = [end, start_2]

        if sum(next_cut) > 0 and next_cut[0] != next_cut[1]:
            next_cut.sort()
            next_cut.append(False)
            cuts.append(next_cut)

    return cuts
