import os
import re
from typing import Dict, Any, Optional

# Regex patterns for cleaning brackets/parentheses noise
NOISE_PATTERNS = [
    r"\[flac\]", r"\(flac\)", r"\[lossless\]", r"\(lossless\)",
    r"\[320(kbps)?\]", r"\(320(kbps)?\)", r"\[web\]", r"\(web\)",
    r"\(official\s+video\)", r"\(official\s+audio\)", r"\(lyric\s+video\)",
    r"\(explicit\)", r"\[explicit\]", r"\[cd\]", r"\(cd\)",
    r"\[remastered\]", r"\(remastered\)"
]

# Patterns for multi-disc prefixes, e.g., "CD1 - 02 - ", "CD 1 - 02 - ", "1-02 - ", "CD1-02 "
MULTI_DISC_REGEXES = [
    re.compile(r"^(?:CD|DISC)\s*(\d+)\s*[-_.\s]+\s*(\d+)\s*[-_.\s]+", re.IGNORECASE),
    re.compile(r"^(\d+)-(\d+)\s*[-_.\s]+", re.IGNORECASE),
]

# Standard track number prefixes, e.g., "01 - ", "01. ", "01 ", "01_ "
TRACK_PREFIX_REGEXES = [
    re.compile(r"^(\d+)\s*-\s*"),
    re.compile(r"^(\d+)\.\s*"),
    re.compile(r"^(\d+)_\s*"),
    re.compile(r"^(\d+)\s+"),
]

def clean_noise(text: str) -> str:
    """Removes standard bracketed and parenthesized noise/codec flags."""
    cleaned = text
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    # Remove empty brackets/parentheses left behind
    cleaned = re.sub(r"\[\s*\]", "", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    # Standardize spaces
    cleaned = " ".join(cleaned.split())
    # Strip leading/trailing dashes, underscores, spaces
    return cleaned.strip(" -_.\t\n\r")

def parse_filename(filename: str) -> Dict[str, Any]:
    """
    Parses a filename into structured metadata.
    Supports:
    - Artist - Track
    - Artist - Album - Track
    - Scene releases (e.g. Artist-Track-2024-GRP)
    - Track prefix patterns and multi-disc formats.
    """
    # Get basename and strip extension
    basename = os.path.basename(filename)
    name_without_ext, ext = os.path.splitext(basename)
    ext = ext.lstrip(".").lower()

    # Clean the name first
    cleaned_name = clean_noise(name_without_ext)

    disc_number: Optional[int] = None
    track_number: Optional[int] = None

    # Try matching multi-disc prefixes
    matched_disc = False
    for regex in MULTI_DISC_REGEXES:
        m = regex.match(cleaned_name)
        if m:
            disc_number = int(m.group(1))
            track_number = int(m.group(2))
            cleaned_name = cleaned_name[m.end():].strip(" -_.\t")
            matched_disc = True
            break

    # If no disc prefix matched, try matching simple track prefix
    if not matched_disc:
        for regex in TRACK_PREFIX_REGEXES:
            m = regex.match(cleaned_name)
            if m:
                track_number = int(m.group(1))
                cleaned_name = cleaned_name[m.end():].strip(" -_.\t")
                break

    # Split patterns:
    # 1. Try splitting by double/triple hyphens or spaces with hyphen
    parts = [p.strip() for p in re.split(r"\s+-\s+", cleaned_name) if p.strip()]

    artist = "Unknown"
    track = "Unknown"
    album = ""
    year: Optional[int] = None

    if len(parts) >= 3:
        # e.g., Artist - Album - Track
        artist = parts[0]
        album = parts[1]
        track = parts[2]
    elif len(parts) == 2:
        # e.g., Artist - Track
        artist = parts[0]
        track = parts[1]
    elif len(parts) == 1:
        # Check if it looks like a scene release:
        # Typically uses underscores or dots inside words, and single hyphens to separate artist, track, year, group.
        # e.g., Kendrick_Lamar-Not_Like_Us-2024-GRP or Kendrick.Lamar-Not.Like.Us-2024-GRP
        # Let's split on hyphens first
        scene_parts = [p.strip() for p in cleaned_name.split("-") if p.strip()]
        if len(scene_parts) >= 2:
            # Check if any part is a 4-digit year
            year_idx = -1
            for idx, p in enumerate(scene_parts):
                if re.match(r"^(19|20)\d{2}$", p):
                    year_idx = idx
                    year = int(p)
                    break

            if year_idx != -1:
                # We can deduce parts around the year
                # e.g. Artist-Track-2024-GRP
                # Artist and Track are before year
                artist_raw = scene_parts[0]
                track_raw = "-".join(scene_parts[1:year_idx]) if year_idx > 1 else scene_parts[1]

                # Replace underscores/dots with spaces
                artist = " ".join(artist_raw.replace("_", " ").replace(".", " ").split())
                track = " ".join(track_raw.replace("_", " ").replace(".", " ").split())
            else:
                # If no year but contains single hyphen, split it as Artist - Track
                artist_raw = scene_parts[0]
                track_raw = "-".join(scene_parts[1:])
                artist = " ".join(artist_raw.replace("_", " ").replace(".", " ").split())
                track = " ".join(track_raw.replace("_", " ").replace(".", " ").split())
        else:
            # Fallback when there is no delimiter
            # Convert underscores/dots to spaces
            normalized = " ".join(cleaned_name.replace("_", " ").replace(".", " ").split())
            track = normalized

    # Clean final fields of remaining leading/trailing punctuation or small artifacts
    artist = artist.strip(" -_.")
    track = track.strip(" -_.")
    album = album.strip(" -_.") if album else ""

    return {
        "artist": artist or "Unknown",
        "track": track or "Unknown",
        "album": album,
        "year": year,
        "disc_number": disc_number,
        "track_number": track_number,
        "format": ext
    }
