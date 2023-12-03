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
from pathlib import Path
from typing import List

from .constant import MARGIN, MIN_LENGTH, THRESHOLD
from .edit import fill_sequence, framerate, get_silence_cuts
from .xml_maker import xml_maker


def main(input_path, min_length=MIN_LENGTH, margin=MARGIN, threshold=THRESHOLD, audio_files=None):
    # type: (Path, float, int, int, List[Path]) -> None
    min_length_frame = min_length * framerate(input_path)

    if audio_files:
        audio_file = audio_files[0]
    else:
        audio_file = None

    cuts = get_silence_cuts(input_path, min_length_frame, threshold, margin, audio_file=audio_file)
    cuts = fill_sequence(input_path, cuts, min_length_frame)

    xml_maker(input_path, cuts, threshold, audio_files=audio_files)
