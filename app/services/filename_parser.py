import os
import re
from typing import Dict, Any, Optional, List

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

# Generic folder names to ignore as Artist/Album candidates
GENERIC_FOLDERS = {
    "share", "downloads", "music", "electronic", "hip-hop", "hip hop", "rock", "pop",
    "metal", "jazz", "classical", "rap", "r&b", "soul", "reggae", "various artists",
    "various", "va", "single", "singles", "albums", "music library", "uncorted", "new",
    "temp", "sorted", "completed", "incoming", "mp3", "flac"
}

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

def extract_featured_artists(text: str) -> tuple[str, List[str]]:
    """
    Extracts featured artists from a string.
    Returns (cleaned_text, list_of_featured_artists).
    Supports: "feat. Artist", "ft. Artist", "featuring Artist", "with Artist".
    """
    featured = []
    # Match patterns like (feat. Kendrick Lamar) or feat Kendrick Lamar
    pattern = re.compile(
        r"[\(\[\s]\s*\b(feat|ft|featuring|with)\b\.?\s+([^\)\]]+)[\)\]]?",
        re.IGNORECASE
    )

    matches = list(pattern.finditer(text))
    cleaned = text

    if matches:
        # Process from back to front to safely remove from string
        for m in reversed(matches):
            raw_artists = m.group(2).strip()
            # Split featured artists by comma, "and", "&"
            split_artists = re.split(r",\s*|\s+and\s+|\s+&\s+", raw_artists, flags=re.IGNORECASE)
            for a in split_artists:
                a_clean = a.strip(" -_.\t\n\r")
                if a_clean:
                    featured.append(a_clean)
            # Strip the matched group from the text
            start, end = m.span()
            cleaned = cleaned[:start] + cleaned[end:]

    # Also search without brackets (e.g. "... feat Kendrick Lamar")
    pattern_nobracket = re.compile(
        r"\s+\b(feat|ft|featuring|with)\b\.?\s+([^,]+)",
        re.IGNORECASE
    )
    m = pattern_nobracket.search(cleaned)
    if m:
        raw_artists = m.group(2).strip()
        split_artists = re.split(r",\s*|\s+and\s+|\s+&\s+", raw_artists, flags=re.IGNORECASE)
        for a in split_artists:
            a_clean = a.strip(" -_.\t\n\r")
            if a_clean:
                featured.append(a_clean)
        cleaned = cleaned[:m.start()]

    return " ".join(cleaned.split()).strip(" -_.\t\n\r"), featured

def parse_filename(filepath: str) -> Dict[str, Any]:
    """
    Intelligently parses a Soulseek file path or standalone filename.
    Extracts Artist, Track, Album, Year, and structural metadata.
    Reduces "Unknown" rates by analyzing directory folder structures.
    """
    # Replace backslashes to standardize path delimiters
    standard_path = filepath.replace("\\", "/")
    parts_path = [p.strip() for p in standard_path.split("/") if p.strip()]

    if not parts_path:
        return {
            "artist": "Unknown", "track": "Unknown", "album": "", "year": None,
            "disc_number": None, "track_number": None, "format": "",
            "is_acapella": False, "is_remix": False, "featured_artists": []
        }

    # Extract filename and extension
    basename = parts_path[-1]
    name_without_ext, ext = os.path.splitext(basename)
    ext = ext.lstrip(".").lower()

    # Determine acapella/instrumental/remix flags from full path
    is_acapella = bool(re.search(r"\b(acapella|acappella|a\s+cappella|vocal|vocals|instrumental)\b", filepath, re.IGNORECASE))
    is_remix = bool(re.search(r"\b(remix|rmx|rework|edit|mix|club\s+mix|extended\s+mix)\b", filepath, re.IGNORECASE))

    # Clean brackets noise
    cleaned_name = clean_noise(name_without_ext)

    # Extract featured artists
    cleaned_name, featured_artists = extract_featured_artists(cleaned_name)

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

    # Split filename elements
    filename_splits = [p.strip() for p in re.split(r"\s+-\s+", cleaned_name) if p.strip()]

    artist = "Unknown"
    track = "Unknown"
    album = ""
    year: Optional[int] = None

    # Step 1: Standard splits in the file name
    if len(filename_splits) >= 3:
        artist = filename_splits[0]
        album = filename_splits[1]
        track = filename_splits[2]
    elif len(filename_splits) == 2:
        artist = filename_splits[0]
        track = filename_splits[1]
    elif len(filename_splits) == 1:
        # Check if scene release with dots or underscores
        scene_parts = [p.strip() for p in cleaned_name.split("-") if p.strip()]
        if len(scene_parts) >= 2:
            year_idx = -1
            for idx, p in enumerate(scene_parts):
                if re.match(r"^(19|20)\d{2}$", p):
                    year_idx = idx
                    year = int(p)
                    break

            if year_idx != -1:
                artist_raw = scene_parts[0]
                track_raw = "-".join(scene_parts[1:year_idx]) if year_idx > 1 else scene_parts[1]
                artist = " ".join(artist_raw.replace("_", " ").replace(".", " ").split())
                track = " ".join(track_raw.replace("_", " ").replace(".", " ").split())
            else:
                artist_raw = scene_parts[0]
                track_raw = "-".join(scene_parts[1:])
                artist = " ".join(artist_raw.replace("_", " ").replace(".", " ").split())
                track = " ".join(track_raw.replace("_", " ").replace(".", " ").split())
        else:
            normalized = " ".join(cleaned_name.replace("_", " ").replace(".", " ").split())
            track = normalized

    # Step 2: Intelligent Directory Inference (Task 6)
    # If artist or album are still "Unknown", traverse directory levels backward
    # @@jqxww\share\Electronic\Flying Lotus\You are dead!\05 - Never Catch Me
    # parts_path[-1] is filename
    # parts_path[-2] is parent folder (You are dead!)
    # parts_path[-3] is grandparent folder (Flying Lotus)

    # Extract any year inside parentheses/brackets from folder names
    for part in parts_path[:-1]:
        year_match = re.search(r"\b(19|20)\d{2}\b", part)
        if year_match and not year:
            year = int(year_match.group(0))

    if artist == "Unknown" or not artist:
        # First check if parent folder contains structured "Artist - Album" or "Year - Artist - Album"
        if len(parts_path) >= 2:
            parent = parts_path[-2]
            parent_clean = clean_noise(parent)
            p_splits = [p.strip() for p in re.split(r"\s+-\s+", parent_clean) if p.strip()]
            if len(p_splits) >= 2 and parent_clean.lower() not in GENERIC_FOLDERS and not parent_clean.startswith("@@"):
                if re.match(r"^\(?\b(19|20)\d{2}\b\)?$", p_splits[0]):
                    if not year:
                        year = int(re.search(r"\b(19|20)\d{2}\b", p_splits[0]).group(0))
                    artist = p_splits[1]
                    if not album and len(p_splits) >= 3:
                        album = " - ".join(p_splits[2:])
                else:
                    artist = p_splits[0]
                    if not album:
                        album = " - ".join(p_splits[1:])

        # Check if grandparent is valid artist folder if artist is still Unknown
        if (artist == "Unknown" or not artist) and len(parts_path) >= 3:
            gp = parts_path[-3]
            parent = parts_path[-2]

            gp_clean = clean_noise(gp)
            parent_clean = clean_noise(parent)

            if gp_clean.lower() not in GENERIC_FOLDERS and not gp_clean.startswith("@@"):
                artist = gp_clean
                if not album and parent_clean.lower() not in GENERIC_FOLDERS:
                    album = parent_clean
        # Alternatively, if only 1 parent directory exists
        elif (artist == "Unknown" or not artist) and len(parts_path) >= 2:
            parent = parts_path[-2]
            parent_clean = clean_noise(parent)
            if parent_clean.lower() not in GENERIC_FOLDERS and not parent_clean.startswith("@@"):
                artist = parent_clean

    if not album:
        if len(parts_path) >= 2:
            parent = parts_path[-2]
            parent_clean = clean_noise(parent)
            if parent_clean.lower() not in GENERIC_FOLDERS and parent_clean != artist and not parent_clean.startswith("@@"):
                album = parent_clean

    # Clean final fields of leading/trailing artifacts
    artist = artist.strip(" -_.\t\n\r")
    track = track.strip(" -_.\t\n\r")
    album = album.strip(" -_.\t\n\r") if album else ""

    # Ensure we fall back to "Unknown" rather than empty string for artist and track
    if not artist:
        artist = "Unknown"
    if not track:
        track = "Unknown"

    return {
        "artist": artist,
        "track": track,
        "album": album,
        "year": year,
        "disc_number": disc_number,
        "track_number": track_number,
        "format": ext,
        "is_acapella": is_acapella,
        "is_remix": is_remix,
        "featured_artists": featured_artists
    }
