"""Local, request-scoped conversion. No user data is retained."""
import io
import json
import zipfile
import xml.etree.ElementTree as ET
import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError

class ConversionError(Exception):
    pass

IMAGE_FORMATS = {'jpg': 'JPEG', 'jpeg': 'JPEG', 'png': 'PNG', 'webp': 'WEBP', 'bmp': 'BMP', 'tiff': 'TIFF', 'tif': 'TIFF', 'gif': 'GIF'}
IMAGE_OUTPUTS = {'jpg', 'png', 'webp', 'bmp', 'tiff'}
VIDEO_FORMATS = {'mp4', 'webm'}
AUDIO_FORMATS = {'mp3', 'wav', 'ogg', 'm4a'}
MAX_IMAGE_PIXELS = int(os.getenv('MAX_IMAGE_PIXELS', '16000000'))
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
MEDIA_INPUTS = ['-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,matroska,webm,avi,mp3,wav,ogg,flac,aac,asf']
DOC_FORMATS = {'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'odt', 'odp', 'ods', 'rtf', 'txt'}


def run_command(args: list[str], timeout: int = 150):
    try:
        res = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise ConversionError('This converter is unavailable on this server. Please try again later.') from exc
    except subprocess.TimeoutExpired as exc:
        raise ConversionError('Conversion timed out. Try a smaller file.') from exc
    if res.returncode != 0:
        raise ConversionError('Could not convert this file. Check that it is valid, unencrypted and contains the required media.')


def _encode_image(img: Image.Image, fmt: str, quality: int):
    stream = io.BytesIO()
    if fmt in {'jpg', 'jpeg'}:
        if img.mode != 'RGB':
            base = Image.new('RGB', img.size, '#ffffff')
            if 'A' in img.getbands():
                base.paste(img, mask=img.getchannel('A'))
            else:
                base.paste(img.convert('RGB'))
            img = base
        img.save(stream, format='JPEG', quality=quality, optimize=True, progressive=True)
    elif fmt == 'webp':
        img.save(stream, format='WEBP', quality=quality, method=4)
    elif fmt == 'bmp':
        img.convert('RGB').save(stream, format='BMP')
    elif fmt == 'tiff':
        img.save(stream, format='TIFF', compression='tiff_deflate')
    else:
        # Lossless PNG can only be reduced by changing dimensions or colours.
        if quality < 80:
            colors = max(16, int(256 * quality / 90))
            if 'A' in img.getbands():
                pal = img.convert('RGBA').quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
            else:
                pal = img.convert('RGB').quantize(colors=colors)
            pal.save(stream, format='PNG', optimize=True)
        else:
            img.save(stream, format='PNG', optimize=True)
    return stream.getvalue()


def convert_image(source: Path, destination: Path, fmt: str, target_bytes: int | None,
                  max_width: int | None, max_height: int | None,
                  resize_mode: str = 'contain',
                  crop: tuple[int, int, int, int] | None = None):
    """Resize by a chosen fit rule, then attempt to respect a file-size ceiling.

    - contain: aspect-preserving maximum bounds (may be smaller than width x height)
    - cover: exact canvas, centre crop
    - pad: exact canvas, background fill (transparent PNG/WEBP, white JPEG)
    - stretch: exact canvas, distortion explicitly requested
    Exact dimensions are never silently changed to satisfy the file target.
    """
    try:
        with Image.open(source) as input_image:
            if input_image.width * input_image.height > MAX_IMAGE_PIXELS:
                raise ConversionError(f'Image exceeds the {MAX_IMAGE_PIXELS // 1000000}-megapixel limit.')
            if input_image.format != IMAGE_FORMATS.get(source.suffix.lower().lstrip('.')):
                raise ConversionError('Image content does not match its filename extension.')
            input_image.load()
            img = ImageOps.exif_transpose(input_image)
            if crop is not None:
                x, y, w, h = crop
                if x < 0 or y < 0 or w < 1 or h < 1 or x + w > img.width or y + h > img.height:
                    raise ConversionError('Invalid crop selection for this image.')
                img = img.crop((x, y, x + w, y + h))
            if img.mode in {'P', 'LA'}:
                img = img.convert('RGBA')
            elif img.mode not in {'RGB', 'RGBA'}:
                img = img.convert('RGB')
            if max_width and max_height and max_width * max_height > MAX_IMAGE_PIXELS:
                raise ConversionError('Requested dimensions exceed the image pixel limit. Lower width or height.')
            if max_width or max_height:
                width, height = max_width, max_height
                if width and height and resize_mode == 'cover':
                    img = ImageOps.fit(img, (width, height), method=Image.Resampling.LANCZOS)
                elif width and height and resize_mode == 'pad':
                    background = (255, 255, 255, 0) if fmt in {'png', 'webp'} else (255, 255, 255)
                    img = ImageOps.pad(img.convert('RGBA'),
                                       (width, height), method=Image.Resampling.LANCZOS, color=background)
                elif width and height and resize_mode == 'stretch':
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                else:
                    # Preserve ratio. A single supplied dimension adjusts that axis,
                    # two supplied dimensions are maximum bounding limits.
                    if width and not height:
                        height = max(1, round(img.height * width / img.width))
                    elif height and not width:
                        width = max(1, round(img.width * height / img.height))
                    img.thumbnail((width or img.width, height or img.height), Image.Resampling.LANCZOS)
            candidates = [100, 75, 50, 25, 10] if fmt == 'png' else (
                [100] if fmt in {'bmp', 'tiff'} else [95, 85, 75, 60, 45, 30, 20, 10])
            smallest = None
            # Fixed dimensions stay fixed whenever explicit width/height were requested.
            can_shrink = not bool(max_width or max_height)
            for _ in range(14 if can_shrink else 1):
                for quality in candidates:
                    encoded = _encode_image(img, fmt, quality)
                    if smallest is None or len(encoded) < len(smallest):
                        smallest = encoded
                    if target_bytes is None or len(encoded) <= target_bytes:
                        destination.write_bytes(encoded)
                        return
                if not can_shrink or min(img.size) <= 24:
                    break
                img = img.resize((max(1, int(img.width * .82)), max(1, int(img.height * .82))),
                                 Image.Resampling.LANCZOS)
            raise ConversionError(
                f'Cannot achieve the requested size at these dimensions. '
                f'Minimum tried: {len(smallest or b"") / 1024:.1f} KB. '
                'Increase size limit, lower dimensions, or try JPG/WEBP.')
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ConversionError('Image exceeds the safe pixel limit. Choose a smaller image.') from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ConversionError('Invalid or unsupported image file.') from exc


def _media_info(source: Path):
    try:
        res = subprocess.run(['ffprobe', '-v', 'error', *MEDIA_INPUTS,
                              '-show_format', '-show_streams', '-of', 'json', str(source)],
                             capture_output=True, text=True, timeout=20)
        info = json.loads(res.stdout)
        duration = float(info['format']['duration'])
        if res.returncode or not (0 < duration < 60 * 60 * 2):
            raise ValueError()
        return duration, info.get('streams', [])
    except FileNotFoundError as exc:
        raise ConversionError('Media conversion is unavailable on this server.') from exc
    except subprocess.TimeoutExpired as exc:
        raise ConversionError('Reading media timed out. Try a smaller file.') from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise ConversionError('Could not read media duration. Use a valid audio/video file shorter than 2 hours.') from exc


def convert_video(source: Path, destination: Path, fmt: str, target_bytes: int | None,
                  width: int | None):
    duration, streams = _media_info(source)
    if not any(s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic') for s in streams):
        raise ConversionError('This file contains no video stream. Choose Audio to convert sound only.')
    scale = ['-vf', f'scale=trunc(min(iw\\,{width or 8192})/2)*2:trunc(ih*min(1\\,{width or 8192}/iw)/2)*2']
    for attempt in range(3):
        if target_bytes:
            # Allow space for muxing headers / variable codec bitrate.
            total_bitrate = int((target_bytes * 8 / duration) * (.83 - attempt * .12))
            audio_rate = 64_000 if total_bitrate < 250_000 else 96_000
            video_rate = total_bitrate - audio_rate
            if video_rate < 55_000:
                raise ConversionError('Requested target size is too small for the video duration.')
            rate_args = ['-b:v', str(video_rate), '-maxrate', str(video_rate), '-bufsize', str(video_rate * 2),
                         '-b:a', str(audio_rate)]
        else:
            rate_args = ['-crf', '30' if fmt == 'webm' else '27', '-b:a', '96k']
        codec = ['-c:v', 'libvpx-vp9', '-c:a', 'libopus', '-deadline', 'realtime', '-cpu-used', '6'] if fmt == 'webm' else [
            '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart']
        run_command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-nostdin', *MEDIA_INPUTS, '-threads', '1', '-i', str(source),
                     '-map', '0:v:0', '-map', '0:a:0?', '-map_metadata', '-1', '-filter_threads', '1', *scale, *codec, *rate_args, '-threads', '1', str(destination)], timeout=240)
        if not target_bytes or destination.stat().st_size <= target_bytes:
            return
    raise ConversionError('Unable to meet target size without unacceptable quality. Try a larger target.')


def convert_audio(source: Path, destination: Path, fmt: str, target_bytes: int | None):
    duration, streams = _media_info(source)
    if not any(s.get('codec_type') == 'audio' for s in streams):
        raise ConversionError('This file contains no audio track. Choose a file with sound.')
    codec = {'mp3': 'libmp3lame', 'wav': 'pcm_s16le', 'ogg': 'libvorbis', 'm4a': 'aac'}[fmt]
    if target_bytes:
        bits = int(target_bytes * 8 / duration * .85)
        if bits < 32_000:
            raise ConversionError('Target size is too small for the audio duration.')
        if fmt == 'wav':
            raise ConversionError('WAV is uncompressed; choose MP3, M4A or OGG for a size target.')
        bitrate = max(32, min(256, bits // 1000))
    else:
        bitrate = 160
    run_command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-nostdin', *MEDIA_INPUTS, '-threads', '1', '-i', str(source), '-vn', '-map', '0:a:0', '-map_metadata', '-1',
                 '-c:a', codec, *([] if fmt == 'wav' else ['-b:a', f'{bitrate}k']), '-threads', '1', str(destination)])
    if target_bytes and destination.stat().st_size > target_bytes:
        raise ConversionError('Audio remains above the target. Try a larger size.')


def compress_pdf(source: Path, destination: Path, target_bytes: int | None):
    validate_pdf(source)
    for profile in ['ebook', 'screen', 'default']:
        run_command(['gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.5',
                     f'-dPDFSETTINGS=/{profile}', '-dSAFER', '-dNOPAUSE', '-dQUIET', '-dBATCH',
                     f'-sOutputFile={destination}', str(source)])
        if source.stat().st_size < destination.stat().st_size:
            shutil.copyfile(source, destination)
        if target_bytes is None or destination.stat().st_size <= target_bytes:
            return
    raise ConversionError('PDF could not reach that target. Image-only/scanned PDFs may need a larger size.')


def convert_document(source: Path, dest_dir: Path, stem: str):
    # HOME is per-request so concurrent LibreOffice instances cannot interfere.
    profile_dir = dest_dir / 'lo-profile'
    (profile_dir / 'user').mkdir(parents=True, exist_ok=True)
    (profile_dir / 'user/registrymodifications.xcu').write_text(
        '<oor:items xmlns:oor="http://openoffice.org/2001/registry">'
        '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
        '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>'
        '</item></oor:items>')
    profile = profile_dir.as_uri()
    run_command(['libreoffice', '-env:UserInstallation=' + profile, '--headless', '--norestore', '--nodefault', '--nolockcheck',
                 '--convert-to', 'pdf', '--outdir', str(dest_dir), str(source)], timeout=150)
    pdf = dest_dir / (source.stem + '.pdf')
    if not pdf.exists():
        raise ConversionError('The document could not be converted to PDF.')
    out = dest_dir / (stem + '.pdf')
    if pdf != out:
        pdf.rename(out)
    return out


def pdf_to_docx(source: Path, destination: Path):
    """Extract selectable PDF text into an editable DOCX; complex layout is not retained."""
    from pypdf import PdfReader
    from docx import Document
    try:
        reader = PdfReader(str(source), strict=False)
        if reader.is_encrypted:
            raise ConversionError('Password-protected PDFs are not supported.')
        if len(reader.pages) > 80:
            raise ConversionError('PDF to Word is limited to 80 pages on the free service.')
        document = Document()
        sections = 0
        for i, page in enumerate(reader.pages):
            text = (page.extract_text(extraction_mode='layout') or '') if page.get('/Contents') else ''
            if not text.strip():
                continue
            if i and sections:
                document.add_page_break()
            for paragraph in text.split('\n'):
                paragraph = paragraph.rstrip()
                if paragraph.strip():
                    document.add_paragraph(paragraph)
            sections += 1
        if not sections:
            raise ConversionError('This PDF has no selectable text. Scanned PDFs need OCR, which is not available yet.')
        document.save(str(destination))
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError('Could not extract text from this PDF.') from exc


def validate_pdf(source):
    from pypdf import PdfReader
    try:
        reader = PdfReader(source)
        if reader.is_encrypted:
            raise ConversionError('Password-protected PDFs are not supported.')
        if not reader.pages or len(reader.pages) > 80:
            raise ConversionError('PDF conversion is limited to 1–80 pages.')
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError('Invalid or damaged PDF file.') from exc


def validate_content(source: Path, category: str):
    """Reject disguised containers and dangerous document features before native tools."""
    with source.open('rb') as handle:
        header = handle.read(4096)
    ext = source.suffix.lower()[1:]
    if category == 'pdf':
        if not header.startswith(b'%PDF-'):
            raise ConversionError('File content is not a PDF.')
        validate_pdf(source)
    elif category == 'document':
        if ext in {'docx', 'pptx', 'xlsx', 'odt', 'odp', 'ods'}:
            try:
                with zipfile.ZipFile(source) as archive:
                    entries = archive.infolist()
                    if len(entries) > 5000 or sum(e.file_size for e in entries) > 100 * 1024 * 1024:
                        raise ConversionError('Document archive is too large when expanded.')
                    names = archive.namelist()
                    required = {'docx': 'word/document.xml', 'pptx': 'ppt/presentation.xml',
                                'xlsx': 'xl/workbook.xml', 'odt': 'content.xml',
                                'odp': 'content.xml', 'ods': 'content.xml'}[ext]
                    if required not in names:
                        raise ConversionError('Document content does not match its extension.')
                    if any('vbaproject' in n.lower() or '/embeddings/' in n.lower() or n.startswith('Basic/') for n in names):
                        raise ConversionError('Documents containing macros or embedded objects are not supported.')
                    for name in names:
                        if name.endswith('.rels') or name == 'content.xml':
                            root = ET.fromstring(archive.read(name))
                            for element in root.iter():
                                # Hyperlinks are inert in export. External images/templates can trigger fetches.
                                if element.get('TargetMode') == 'External' and not element.get('Type', '').endswith('/hyperlink'):
                                    raise ConversionError('Remove linked external resources before converting this document.')
                                for attribute, value in element.attrib.items():
                                    if attribute.endswith('}href') and (':' in value or value.startswith('/')) and not element.tag.endswith('}a'):
                                        raise ConversionError('Remove linked external resources before converting this document.')
            except ConversionError:
                raise
            except (zipfile.BadZipFile, ET.ParseError, RuntimeError, KeyError) as exc:
                raise ConversionError('Invalid or damaged document archive.') from exc
        elif ext in {'doc', 'ppt', 'xls'}:
            if not header.startswith(bytes.fromhex('D0CF11E0A1B11AE1')):
                raise ConversionError('File content does not match this Office document format.')
        elif ext == 'rtf':
            if not header.lstrip().startswith(b'{\\rtf'):
                raise ConversionError('Invalid RTF document.')
        elif ext == 'txt':
            try:
                text = source.read_bytes().decode('utf-8-sig')
            except UnicodeDecodeError as exc:
                raise ConversionError('Please save text files as UTF-8 before converting.') from exc
            if '\x00' in text or text.lstrip().startswith(('<', '{\\rtf')):
                raise ConversionError('Upload plain UTF-8 text, not markup or binary content.')
