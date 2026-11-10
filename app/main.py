import asyncio
import os
import re
import math
import logging
import time
import tempfile
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.datastructures import UploadFile as StarletteUploadFile
from .security import RequestGuards
from .seo import TOOLS, tool_page, sitemap, robots
from .jobs import run_job
from .processor import (AUDIO_FORMATS, DOC_FORMATS, IMAGE_FORMATS, IMAGE_OUTPUTS,
                        VIDEO_FORMATS, ConversionError)


class StaticGZip(GZipMiddleware):
    async def __call__(self, scope, receive, send):
        if scope.get('path') == '/' or scope.get('path', '').startswith('/static/'):
            return await super().__call__(scope, receive, send)
        return await self.app(scope, receive, send)


class DownloadResponse(FileResponse):
    def __init__(self, *args, cleanup, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleanup = cleanup

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.cleanup()


ROOT = Path(__file__).parent
MAX_UPLOAD = int(os.getenv('MAX_UPLOAD_MB', '80')) * 1024 * 1024
CONCURRENT_JOBS = asyncio.Semaphore(int(os.getenv('MAX_JOBS', '1')))
app = FastAPI(title='Free All-in Converter', version='2.0.0', docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(RequestGuards, max_body=MAX_UPLOAD + 65536,
                   max_active=int(os.getenv('MAX_PENDING_REQUESTS', '3')),
                   rate_limit=int(os.getenv('RATE_LIMIT_PER_MINUTE', '12')))
app.add_middleware(StaticGZip, minimum_size=1024, compresslevel=5)
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')

@app.get('/', response_class=HTMLResponse)
async def index():
    return (ROOT / 'static/index.html').read_text(encoding='utf-8')

@app.get('/tools/{slug}', response_class=HTMLResponse)
async def conversion_tool_page(slug: str):
    if slug not in TOOLS:
        raise HTTPException(404, 'Converter page not found.')
    return tool_page(slug)

@app.get('/sitemap.xml')
async def sitemap_xml():
    return Response(sitemap(), media_type='application/xml')

@app.get('/robots.txt')
async def robots_txt():
    return PlainTextResponse(robots())

@app.get('/health')
async def health():
    return {'status': 'ok', 'app': 'free-all-in-converter'}

@app.get('/api/capabilities')
async def capabilities():
    return {'max_upload_mb': MAX_UPLOAD // (1024*1024),
            'max_image_pixels': int(os.getenv('MAX_IMAGE_PIXELS', '16000000')),
            'supported': {'image': sorted(IMAGE_OUTPUTS), 'video': sorted(VIDEO_FORMATS),
                          'audio': sorted(AUDIO_FORMATS), 'pdf': ['pdf', 'docx'], 'document': ['pdf']},
            'inputs': {'image': sorted(IMAGE_FORMATS), 'video': ['mp4', 'webm', 'mov', 'mkv', 'avi'],
                       'audio': sorted(AUDIO_FORMATS | {'flac', 'aac', 'wma', 'mp4', 'webm', 'mov', 'mkv', 'avi'}),
                       'pdf': ['pdf'], 'document': sorted(DOC_FORMATS)}}

@app.post('/api/convert')
async def convert(request: Request, file: UploadFile = File(...), category: str = Form(...),
                  output_format: str = Form(...), target_mb: float | None = Form(None),
                  max_width: int | None = Form(None), max_height: int | None = Form(None),
                  resize_mode: str = Form('contain'),
                  crop_x: int | None = Form(None), crop_y: int | None = Form(None),
                  crop_width: int | None = Form(None), crop_height: int | None = Form(None)):
    parts = (await request.form()).multi_items()
    if sum(isinstance(value, StarletteUploadFile) for _, value in parts) != 1:
        raise HTTPException(422, 'Upload exactly one file at a time.')
    if len({name for name, _ in parts}) != len(parts):
        raise HTTPException(422, 'Send each conversion setting only once.')
    fmt = output_format.lower().lstrip('.')
    category = category.lower()
    ext = Path(file.filename or '').suffix.lower().lstrip('.')
    accepted = (set(IMAGE_FORMATS) if category == 'image' else
                VIDEO_FORMATS | {'mov', 'mkv', 'avi'} if category == 'video' else
                AUDIO_FORMATS | {'flac', 'aac', 'wma', 'mp4', 'webm', 'mov', 'mkv', 'avi'} if category == 'audio' else
                {'pdf'} if category == 'pdf' else DOC_FORMATS if category == 'document' else set())
    outputs = (IMAGE_OUTPUTS if category == 'image' else
               VIDEO_FORMATS if category == 'video' else
               AUDIO_FORMATS if category == 'audio' else
               {'pdf', 'docx'} if category == 'pdf' else
               {'pdf'} if category == 'document' else set())
    if ext not in accepted or fmt not in outputs:
        raise HTTPException(422, 'Unsupported input or output format for this category.')
    if target_mb is not None and not (math.isfinite(target_mb) and 1/1024 <= target_mb <= 500):
        raise HTTPException(422, 'Target must be between 1 KB and 500 MB.')
    if resize_mode not in {'contain', 'cover', 'pad', 'stretch'}:
        raise HTTPException(422, 'Invalid image resizing mode.')
    if category not in {'image', 'video'} and (max_width is not None or max_height is not None):
        raise HTTPException(422, 'Dimensions apply only to images and video.')
    if category == 'video' and max_height is not None:
        raise HTTPException(422, 'Video supports maximum width only.')
    min_width = 64 if category == 'video' else 1
    if max_width is not None and not (min_width <= max_width <= 8192):
        raise HTTPException(422, f'Width must be between {min_width} and 8192 pixels.')
    if max_height is not None and not (1 <= max_height <= 8192):
        raise HTTPException(422, 'Height must be between 1 and 8192 pixels.')
    crop_params = (crop_x, crop_y, crop_width, crop_height)
    if any(value is not None for value in crop_params) and (category != 'image' or not all(value is not None for value in crop_params)):
        raise HTTPException(422, 'Crop requires four image coordinates.')
    if (not file.filename or len(file.filename) > 180 or '\x00' in file.filename
            or '/' in file.filename or '\\' in file.filename or any(ord(c) < 32 for c in file.filename)):
        raise HTTPException(422, 'Please use a valid filename.')
    temp = tempfile.TemporaryDirectory(prefix='convertlab-')
    directory = Path(temp.name)
    source = directory / f'input.{ext}'
    target_bytes = int(target_mb * 1024 * 1024) if target_mb else None
    try:
        total = 0
        with source.open('wb') as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD:
                    raise HTTPException(413, f'Maximum upload size is {MAX_UPLOAD // (1024*1024)} MB.')
                out.write(chunk)
        if not total:
            raise HTTPException(422, 'Please choose a nonempty file.')
        destination = directory / f'converted.{fmt}'
        started = time.monotonic()
        try:
            await asyncio.wait_for(CONCURRENT_JOBS.acquire(), timeout=5)
        except asyncio.TimeoutError:
            raise HTTPException(503, 'The converter is busy. Please try again shortly.', headers={'Retry-After': '5'})
        try:
            await run_job({'source': str(source), 'destination': str(destination),
                           'category': category, 'fmt': fmt, 'target': target_bytes,
                           'width': max_width, 'height': max_height, 'resize': resize_mode,
                           'crop': crop_params if all(value is not None for value in crop_params) else None})
        finally:
            CONCURRENT_JOBS.release()
        if not destination.exists() or destination.stat().st_size == 0:
            raise ConversionError('No output was produced.')
        logging.getLogger('uvicorn.error').info('conversion category=%s outcome=ok duration_ms=%d', category, (time.monotonic()-started)*1000)
        safe_stem = re.sub(r'[^A-Za-z0-9_-]', '_', Path(file.filename).stem)[:65] or 'file'
        return DownloadResponse(destination, filename=f'{safe_stem}_converted.{fmt}',
                            media_type='application/octet-stream', cleanup=temp.cleanup,
                            headers={'X-Converted-Bytes': str(destination.stat().st_size)})
    except asyncio.CancelledError:
        temp.cleanup()
        raise
    except HTTPException:
        temp.cleanup()
        raise
    except ConversionError as exc:
        temp.cleanup()
        raise HTTPException(422, str(exc)) from exc
    except Exception:
        temp.cleanup()
        raise HTTPException(500, 'An unexpected conversion error occurred.')
    finally:
        await file.close()
