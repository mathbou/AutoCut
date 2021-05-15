from pathlib import Path
from fractions import Fraction
from functools import partial
from multiprocessing import Pool
from typing import List, Tuple, NoReturn, Optional

from xml.etree import ElementTree as ET
from xml.dom import minidom

from .edit import framerate, duration, section_is_quiet, extract_audio, resolution


def Element(elem_name, text=None, **kwargs):
    elem = ET.Element(elem_name)

    if text:
        elem.text = str(text)

    for key, value in kwargs.items():
        elem.set(str(key), str(value))

    return elem


def SubElement(parent, elem_name, text=None, **kwargs):
    elem = Element(elem_name, text, **kwargs)

    parent.append(elem)

    return elem


def sec_to_fraction(value):
    fraction = Fraction(value).limit_denominator()

    if not fraction:
        fraction = "0/1"

    return "{}s".format(str(fraction))


def clip_maker(fps, video_id, audio_files,
               threshold, frame_length,
               cut=None):
    # type: (float, int, List[Path], float, Fraction, Tuple[int, int, bool]) -> ET.Element
    start, end, is_quiet = cut

    print(start, end)

    fr_duration = f"{end-start}/{fps}s"

    fr_start = f"{start}/{fps}s"

    video_clip = Element("video",
                         offset=fr_start,
                         start=fr_start,
                         ref=video_id,
                         duration=fr_duration)

    if is_quiet:
        video_clip.set("lane", "1")

    elif audio_files:
        # Additional audio tracks
        for lane_id, audio_file in enumerate(audio_files):
            if section_is_quiet(audio_file, start, end, threshold, frame_length):
                continue

            SubElement(video_clip, "audio",
                       lane=-2 - lane_id,
                       offset=fr_start,
                       start=fr_start,
                       ref="a{}".format(lane_id + 1),
                       duration=fr_duration)

    return video_clip


def xml_maker(in_file, cuts, threshold, audio_files=None):
    # type: (Path, Tuple[int, int, bool], float, Optional[List[Path]]) -> NoReturn
    fcpxml = Element("fcpxml", version=1.9)

    resources = SubElement(fcpxml, "resources")

    filename = in_file.name
    # _ , ext = os.path.splitext(in_file)

    video_duration = sec_to_fraction(duration(in_file))
    video_width, video_height = resolution(in_file)
    frame_length = framerate(in_file)
    fps = Fraction(1, frame_length)
    video_rate_s = f"{frame_length}s"

    SubElement(resources, "format", name="FFVideoFormatRateUndefined",
               width=video_width,
               id="r0",
               frameDuration=video_rate_s,
               height=video_height)
    SubElement(resources, "format", name="FFVideoFormat1080p24",
               width=1920,
               id="r1",
               frameDuration=video_rate_s,
               height=1080)

    video_id = "v1"
    SubElement(resources, "asset",
               format_="r0",
               name=filename,
               audioChannels=2,
               id=video_id,
               start=sec_to_fraction(0),
               src=in_file.as_posix(),
               hasAudio=1,
               audioSources=1,
               duration=video_duration)

    if not audio_files:
        audio_files = extract_audio(in_file)

    for i, audio_file in enumerate(audio_files):
        SubElement(resources, "asset",
                   name=audio_file.name,
                   audioChannels=2,
                   id="a{}".format(i+1),
                   start=sec_to_fraction(0),
                   src=audio_file.as_posix(),
                   hasAudio=1,
                   audioSources=1,
                   duration=video_duration)


    library = SubElement(fcpxml, "library")
    event = SubElement(library, "event", name=f"Timeline {filename}")
    project = SubElement(event, "project", name=f"Timeline {filename}")
    sequence = SubElement(project, "sequence",
                          format="r1",
                          tcFormat="NDF",
                          tcStart="0/1s",
                          duration=video_duration)
    spine = SubElement(sequence, "spine")

    with Pool() as p:
        func = partial(clip_maker, fps, video_id, audio_files, threshold, frame_length)
        clips = p.map(func, cuts)
        spine.extend(clips)

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