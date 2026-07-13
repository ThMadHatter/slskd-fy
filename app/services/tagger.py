import os
import logging
from typing import Optional, Dict, Any
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TALB, TPE1, TPE2, TRCK, TDRC, TCON, COMM, APIC
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggvorbis import OggVorbis

logger = logging.getLogger("track_portal.tagger")

def write_tags(
    filepath: str,
    title: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    album_artist: Optional[str] = None,
    track_number: Optional[str] = None,
    year: Optional[str] = None,
    genre: Optional[str] = None,
    comment: Optional[str] = None,
    cover_image_bytes: Optional[bytes] = None,
    cover_mime: str = "image/jpeg"
) -> bool:
    """
    Writes audio metadata tags for FLAC, MP3, M4A, and OGG formats using mutagen.
    """
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return False

    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".flac":
            audio = FLAC(filepath)
            if title: audio["title"] = title
            if artist: audio["artist"] = artist
            if album: audio["album"] = album
            if album_artist: audio["albumartist"] = album_artist
            if track_number: audio["tracknumber"] = track_number
            if year: audio["date"] = year
            if genre: audio["genre"] = genre
            if comment: audio["comment"] = comment

            if cover_image_bytes:
                # Remove existing cover art
                audio.clear_pictures()
                pic = Picture()
                pic.data = cover_image_bytes
                pic.type = 3  # Front cover
                pic.mime = cover_mime
                pic.desc = "Front Cover"
                audio.add_picture(pic)

            audio.save()
            logger.info(f"Successfully saved tags for FLAC: {filepath}")
            return True

        elif ext == ".mp3":
            # Ensure ID3 tags are initialized
            try:
                audio = MP3(filepath)
                if audio.tags is None:
                    audio.add_tags()
                tags = audio.tags
            except Exception:
                tags = ID3(filepath)

            if title: tags["TIT2"] = TIT2(encoding=3, text=title)
            if artist: tags["TPE1"] = TPE1(encoding=3, text=artist)
            if album: tags["TALB"] = TALB(encoding=3, text=album)
            if album_artist: tags["TPE2"] = TPE2(encoding=3, text=album_artist)
            if track_number: tags["TRCK"] = TRCK(encoding=3, text=track_number)
            if year: tags["TDRC"] = TDRC(encoding=3, text=year)
            if genre: tags["TCON"] = TCON(encoding=3, text=genre)
            if comment:
                tags["COMM"] = COMM(encoding=3, lang="eng", desc="desc", text=comment)

            if cover_image_bytes:
                # Remove existing APIC
                cover_keys = [k for k in tags.keys() if k.startswith("APIC")]
                for k in cover_keys:
                    del tags[k]
                tags["APIC"] = APIC(
                    encoding=3,
                    mime=cover_mime,
                    type=3,  # Front cover
                    desc="Front Cover",
                    data=cover_image_bytes
                )

            tags.save(filepath)
            logger.info(f"Successfully saved tags for MP3: {filepath}")
            return True

        elif ext in [".m4a", ".mp4"]:
            audio = MP4(filepath)
            if title: audio["\xa9nam"] = [title]
            if artist: audio["\xa9ART"] = [artist]
            if album: audio["\xa9alb"] = [album]
            if album_artist: audio["aART"] = [album_artist]
            if track_number:
                try:
                    num = int(track_number)
                    audio["trkn"] = [(num, 0)]
                except ValueError:
                    logger.warning(f"Invalid track number for M4A: {track_number}")
            if year: audio["\xa9day"] = [year]
            if genre: audio["\xa9gen"] = [genre]
            if comment: audio["\xa9cmt"] = [comment]

            if cover_image_bytes:
                image_format = MP4Cover.FORMAT_JPEG
                if "png" in cover_mime:
                    image_format = MP4Cover.FORMAT_PNG
                audio["covr"] = [MP4Cover(cover_image_bytes, imageformat=image_format)]

            audio.save()
            logger.info(f"Successfully saved tags for M4A: {filepath}")
            return True

        elif ext in [".ogg", ".ogv"]:
            audio = OggVorbis(filepath)
            if title: audio["title"] = title
            if artist: audio["artist"] = artist
            if album: audio["album"] = album
            if album_artist: audio["albumartist"] = album_artist
            if track_number: audio["tracknumber"] = track_number
            if year: audio["date"] = year
            if genre: audio["genre"] = genre
            if comment: audio["comment"] = comment

            # Note: OGG Vorbis covers are complex (METADATA_BLOCK_PICTURE Base64),
            # so we'll save comments and tags, and optionally log.
            audio.save()
            logger.info(f"Successfully saved tags for OGG: {filepath}")
            return True

        else:
            logger.warning(f"Unsupported format for tagging: {ext}")
            return False

    except Exception as e:
        logger.error(f"Error writing tags to {filepath}: {e}")
        return False

def read_tags(filepath: str) -> Dict[str, Any]:
    """
    Reads audio metadata tags and returns a dict with standard keys.
    """
    tags_data = {
        "title": "",
        "artist": "",
        "album": "",
        "album_artist": "",
        "track_number": "",
        "year": "",
        "genre": "",
        "comment": "",
        "has_cover": False
    }

    if not os.path.exists(filepath):
        return tags_data

    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".flac":
            audio = FLAC(filepath)
            tags_data["title"] = audio.get("title", [""])[0]
            tags_data["artist"] = audio.get("artist", [""])[0]
            tags_data["album"] = audio.get("album", [""])[0]
            tags_data["album_artist"] = audio.get("albumartist", [""])[0]
            tags_data["track_number"] = audio.get("tracknumber", [""])[0]
            tags_data["year"] = audio.get("date", [""])[0]
            tags_data["genre"] = audio.get("genre", [""])[0]
            tags_data["comment"] = audio.get("comment", [""])[0]
            tags_data["has_cover"] = len(audio.pictures) > 0

        elif ext == ".mp3":
            audio = MP3(filepath)
            if audio.tags:
                tags_data["title"] = str(audio.tags.get("TIT2", ""))
                tags_data["artist"] = str(audio.tags.get("TPE1", ""))
                tags_data["album"] = str(audio.tags.get("TALB", ""))
                tags_data["album_artist"] = str(audio.tags.get("TPE2", ""))
                tags_data["track_number"] = str(audio.tags.get("TRCK", ""))
                tags_data["year"] = str(audio.tags.get("TDRC", ""))
                tags_data["genre"] = str(audio.tags.get("TCON", ""))

                # Check for comment
                comm = audio.tags.get("COMM::eng") or audio.tags.get("COMM")
                if comm:
                    tags_data["comment"] = str(comm.text[0] if hasattr(comm, 'text') else comm)

                # Check for cover art
                tags_data["has_cover"] = any(k.startswith("APIC") for k in audio.tags.keys())

        elif ext in [".m4a", ".mp4"]:
            audio = MP4(filepath)
            tags_data["title"] = audio.get("\xa9nam", [""])[0]
            tags_data["artist"] = audio.get("\xa9ART", [""])[0]
            tags_data["album"] = audio.get("\xa9alb", [""])[0]
            tags_data["album_artist"] = audio.get("aART", [""])[0]
            tags_data["year"] = audio.get("\xa9day", [""])[0]
            tags_data["genre"] = audio.get("\xa9gen", [""])[0]
            tags_data["comment"] = audio.get("\xa9cmt", [""])[0]

            trkn = audio.get("trkn", [(0, 0)])[0]
            if trkn and trkn[0] > 0:
                tags_data["track_number"] = str(trkn[0])

            tags_data["has_cover"] = "covr" in audio

        elif ext in [".ogg", ".ogv"]:
            audio = OggVorbis(filepath)
            tags_data["title"] = audio.get("title", [""])[0]
            tags_data["artist"] = audio.get("artist", [""])[0]
            tags_data["album"] = audio.get("album", [""])[0]
            tags_data["album_artist"] = audio.get("albumartist", [""])[0]
            tags_data["track_number"] = audio.get("tracknumber", [""])[0]
            tags_data["year"] = audio.get("date", [""])[0]
            tags_data["genre"] = audio.get("genre", [""])[0]
            tags_data["comment"] = audio.get("comment", [""])[0]

    except Exception as e:
        logger.error(f"Error reading tags from {filepath}: {e}")

    return tags_data
