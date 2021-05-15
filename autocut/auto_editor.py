from pathlib import Path
from tkinter import filedialog, Tk

from typing import NoReturn, List

from .xml_maker import xml_maker
from .edit import get_silence_cuts, fill_sequence, framerate


def main(input_path, min_length=1.75, margin=4, threshold=-50, audio_files=None):
    # type: (Path, float, int, int, List[Path]) -> NoReturn
    min_length_frame = min_length * framerate(input_path)

    if audio_files:
        audio_file = audio_files[0]
    else:
        audio_file = None

    cuts = get_silence_cuts(in_path, min_length_frame, threshold, margin, audio_file=audio_file)
    cuts = fill_sequence(in_path, cuts)

    xml_maker(in_path, cuts, threshold, audio_files=audio_files)


if __name__ == '__main__':
    root = Tk()
    root.withdraw()

    video_types = [("Video Files", ".mp4")]
    in_path = filedialog.askopenfilename(initialdir="F:/obs", filetypes=video_types)

    if not in_path:
        exit(0)
    else:
        in_path = Path(in_path)

    audio_types = [("Audio Files", ".mp3 .ogg .wav .flac .aac .m4a")]
    audio_paths = filedialog.askopenfilenames(initialdir="F:/obs", filetypes=audio_types)

    root.destroy()

    audio_file = None
    if audio_paths:
        audio_paths = [ Path(audio_path) for audio_path in audio_paths ]
        audio_file = audio_paths[0]


    main(in_path, audio_files=audio_paths)

    exit(0)