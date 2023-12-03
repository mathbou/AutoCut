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
from fractions import Fraction
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import Any
from xml.dom import minidom
from xml.etree import ElementTree as ET

from .edit import duration, extract_audio, framelength, framerate, resolution, section_is_quiet


def Element(elem_name, text=None, **kwargs):
    # type: (str, str|None, Any) -> ET.Element
    elem = ET.Element(elem_name)

    if text:
        elem.text = str(text)

    for key, value in kwargs.items():
        elem.set(str(key), str(value))

    return elem


def SubElement(parent, elem_name, text=None, **kwargs):
    # type: (ET.Element, str, str|None, Any) -> ET.Element
    elem = Element(elem_name, text, **kwargs)

    parent.append(elem)

    return elem


def sec_to_fraction(value):
    # type: (float) -> str
    fraction = Fraction(value).limit_denominator()

    if not fraction:
        fraction = "0/1"

    return "{}s".format(str(fraction))


def clip_maker(fps, video_id, audio_files, threshold, frame_length, cut=None):
    # type: (Fraction, int, list[Path], float, Fraction, tuple[int, int, bool]) -> ET.Element
    start, end, is_quiet = cut

    fr_duration = f"{(end-start)/fps}s"

    fr_start = f"{start/fps}s"

    video_clip = Element("video", offset=fr_start, start=fr_start, ref=video_id, duration=fr_duration)

    if is_quiet:
        video_clip.set("lane", "1")

    elif audio_files:
        # Additional audio tracks
        for lane_id, audio_file in enumerate(audio_files):
            if section_is_quiet(audio_file, start, end, threshold, frame_length):
                continue

            SubElement(
                video_clip,
                "audio",
                lane=-2 - lane_id,
                offset=fr_start,
                start=fr_start,
                ref="a{}".format(lane_id + 1),
                duration=fr_duration,
            )

    return video_clip


def xml_maker(in_file, cuts, threshold, audio_files=None):
    # type: (Path, tuple[int, int, bool], float, list[Path]|None) -> None
    print("Compute Xml")

    fcpxml = Element("fcpxml", version=1.9)

    resources = SubElement(fcpxml, "resources")

    filename = in_file.name
    # _ , ext = os.path.splitext(in_file)

    video_duration = sec_to_fraction(duration(in_file))
    video_width, video_height = resolution(in_file)
    fps = framerate(in_file)
    frame_length = framelength(fps)
    video_rate_s = f"{frame_length}s"

    SubElement(
        resources,
        "format",
        name="FFVideoFormatRateUndefined",
        width=video_width,
        id="r0",
        frameDuration=video_rate_s,
        height=video_height,
    )
    SubElement(
        resources, "format", name="FFVideoFormat1080p24", width=1920, id="r1", frameDuration=video_rate_s, height=1080
    )

    video_id = "v1"
    SubElement(
        resources,
        "asset",
        format_="r0",
        name=filename,
        audioChannels=2,
        id=video_id,
        start=sec_to_fraction(0),
        src=in_file.as_posix(),
        hasAudio=1,
        audioSources=1,
        duration=video_duration,
    )

    if not audio_files:
        audio_files = extract_audio(in_file)

    for i, audio_file in enumerate(audio_files):
        SubElement(
            resources,
            "asset",
            name=audio_file.name,
            audioChannels=2,
            id="a{}".format(i + 1),
            start=sec_to_fraction(0),
            src=audio_file.as_posix(),
            hasAudio=1,
            audioSources=1,
            duration=video_duration,
        )

    library = SubElement(fcpxml, "library")
    event = SubElement(library, "event", name=f"Timeline {filename}")
    project = SubElement(event, "project", name=f"Timeline {filename}")
    sequence = SubElement(project, "sequence", format="r1", tcFormat="NDF", tcStart="0/1s", duration=video_duration)
    spine = SubElement(sequence, "spine")

    print("Compute clips")
    with Pool() as p:
        func = partial(clip_maker, fps, video_id, audio_files, threshold, frame_length)
        clips = p.map(func, cuts)
        spine.extend(clips)
    print(f"{len(clips)} clips computed")

    # EXPORT
    datas = ET.tostring(fcpxml)
    doc = minidom.parseString(datas)

    # DOCTYPE
    dt = minidom.getDOMImplementation('').createDocumentType('fcpxml', '', '')
    doc.insertBefore(dt, doc.documentElement)

    datas = doc.toprettyxml(encoding="utf-8")

    out_path = in_file.with_suffix(".fcpxml")
    with open(out_path, "wb") as file_:
        file_.write(datas)
