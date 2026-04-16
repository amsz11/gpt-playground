# iPod Extractor

Extract songs from a mounted iPod with all metadata intact.

## Requirements

- Python 3.10+
- [`mutagen`](https://mutagen.readthedocs.io/) — auto-installed on first run

## Usage

### GUI

```bash
python extract_ipod.py
```

Plug in your iPod before launching — it will be detected automatically. Use the browse buttons to change paths, then hit **EXTRACT**.

### Headless

```bash
python extract_ipod.py /Volumes/MyiPod ~/Music/output
```

## Output layout

Songs are organized by artist and album:

```
output/
  Artist Name/
    Album Name/
      01 - Song Title.mp3
      02 - Another Song.mp3
```

## Notes

- Metadata is read from embedded ID3/AAC tags in each file
- DRM-protected `.m4p` files are copied but will not play without iTunes authorization
- Duplicate filenames are automatically suffixed `(1)`, `(2)`, etc.
