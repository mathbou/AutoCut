# Autocut

This tools detect silence sections in videos and create a FcpX timeline with the video and audio cut accordingly.

> [!note]
> It does not suppress quiet sections, it only cut them and separate them on a second video track.

[TOC]

## 🥰 Support My Work 

If you appreciate my work, consider ⭐ starring this repository or 💰 making a donation to support
future updates and maintenance.

[![](https://img.shields.io/badge/GITHUB%20SPONSOR-30363d?style=for-the-badge&logo=GitHub-Sponsors&logoColor=EA4AAA)](https://github.com/sponsors/mathbou)
[![Static Badge](https://img.shields.io/badge/STRIPE-f6f9fc?style=for-the-badge&logo=stripe)
](https://donate.stripe.com/5kQ3cn9vd0PB5EB75583C00)

## Usage

Two versions are available:

### 👨‍💻 CLI

```shell
autocut-cli [-h] [--audio-file AUDIO_FILE] [--min-length MIN_LENGTH] [--margin MARGIN] [--threshold THRESHOLD] input_path
```

- `audio-file`: Override audio tracks used for silence detection and timeline cuts. Can be used multiple times.
- `min-length` (default=`1.0`): The minimal duration of a quiet section in seconds. 
- `margin` (default=`5`): By how many frames non-quiet cuts are extended. Prevents sudden audio cut. 
- `threshold` (default=`-60`): At which Db level a section is marked "quiet". Should always be negative. 

### 🎛 GUI

```shell
autocut
```

In this mode, you only choose which file to process, all other options use default settings.

