import asyncio
import io
import json
import subprocess
import zipfile
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader, PdfWriter
from app.main import app
from app.security import RequestGuards
from app.processor import ConversionError, run_command

client = TestClient(app)


def upload(content, name='test.png', category='image', output='png', **fields):
    return client.post('/api/convert', files={'file': (name, content)},
                       data={'category': category, 'output_format': output, **fields})


def png(mode='RGB', size=(100, 60), color='red'):
    image = Image.new(mode, size, color)
    stream = io.BytesIO(); image.save(stream, 'PNG')
    return stream.getvalue()


@pytest.mark.parametrize('fmt', ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff', 'tif', 'gif'])
def test_image_input_matrix(fmt):
    stream = io.BytesIO()
    Image.new('RGB', (100, 60), 'red').save(stream, {'jpg':'JPEG','jpeg':'JPEG','tif':'TIFF'}.get(fmt, fmt.upper()))
    r = upload(stream.getvalue(), f'input.{fmt}')
    assert r.status_code == 200, r.text
    assert Image.open(io.BytesIO(r.content)).size == (100, 60)


@pytest.mark.parametrize('fmt', ['jpg', 'png', 'webp', 'bmp', 'tiff'])
def test_image_output_matrix(fmt):
    r = upload(png(), output=fmt)
    assert r.status_code == 200, r.text
    image = Image.open(io.BytesIO(r.content)); image.load()
    assert image.size == (100, 60)
    assert r.headers['content-disposition'] == f'attachment; filename="test_converted.{fmt}"'
    assert int(r.headers['x-converted-bytes']) == len(r.content)


@pytest.mark.parametrize('fields', [dict(target_mb='nan'), dict(target_mb='inf'), dict(max_width=0),
    dict(max_height=8193), dict(crop_x=0), dict(crop_x=-1,crop_y=0,crop_width=20,crop_height=20),
    dict(resize_mode='invalid')])
def test_invalid_parameters(fields):
    r = upload(png(), **fields)
    assert r.status_code == 422, r.text


@pytest.mark.parametrize('name,content', [('test.png', b''), ('test.png', b'<html>bad</html>'),
    ('../test.png', b'bad'), ('test.jpg', png()), ('test.png', b'\x89PNG\r\n\x1a\n')])
def test_invalid_content(name, content):
    r = upload(content, name)
    assert r.status_code == 422, r.text
    assert '/tmp/' not in r.text and 'Traceback' not in r.text


def test_exact_one_kib_and_white_alpha():
    r = upload(png('RGBA', (10,10), (255,0,0,0)), output='jpg', target_mb=1/1024)
    assert r.status_code == 200, r.text
    assert len(r.content) <= 1024
    assert Image.open(io.BytesIO(r.content)).getpixel((0,0)) == (255,255,255)


def test_palette_transparency_jpeg_and_padding():
    im = Image.new('P', (10,10), 0); im.info['transparency'] = 0
    mem=io.BytesIO(); im.save(mem,'PNG')
    r=upload(mem.getvalue(),output='jpg',max_width=20,max_height=20,resize_mode='pad')
    assert r.status_code == 200, r.text
    result=Image.open(io.BytesIO(r.content))
    assert result.size == (20,20)
    assert min(result.getpixel((10,10))) > 245


def test_exif_orientation_before_crop():
    im=Image.new('RGB',(80,40),'blue'); exif=im.getexif(); exif[274]=6
    mem=io.BytesIO(); im.save(mem,'JPEG',exif=exif)
    r=upload(mem.getvalue(),'rotated.jpg',crop_x=0,crop_y=40,crop_width=40,crop_height=40)
    assert r.status_code == 200, r.text
    assert Image.open(io.BytesIO(r.content)).size == (40,40)


def test_pixel_limit_checked_before_decode(monkeypatch,tmp_path):
    import app.processor as p
    source=tmp_path/'test.png'; source.write_bytes(png(size=(100,100)))
    monkeypatch.setattr(p,'MAX_IMAGE_PIXELS',9000)
    with pytest.raises(ConversionError,match='megapixel'):
        p.convert_image(source,tmp_path/'out.png','png',None,None,None)


def test_output_pixel_limit():
    r=upload(png(),max_width=8192,max_height=8192,resize_mode='stretch')
    assert r.status_code == 422 and 'pixel limit' in r.text


def blank_pdf(encrypt=False,pages=1):
    writer=PdfWriter()
    for _ in range(pages):writer.add_blank_page(width=100,height=100)
    if encrypt:writer.encrypt('secret')
    mem=io.BytesIO();writer.write(mem);return mem.getvalue()


def test_scanned_pdf_requires_ocr():
    r=upload(blank_pdf(),'scan.pdf','pdf','docx')
    assert r.status_code == 422 and 'OCR' in r.text


@pytest.mark.parametrize('output',['pdf','docx'])
def test_encrypted_and_page_limit(output):
    r=upload(blank_pdf(True),'secret.pdf','pdf',output)
    assert r.status_code == 422 and 'Password' in r.text
    r=upload(blank_pdf(pages=81),'long.pdf','pdf',output)
    assert r.status_code == 422 and '80' in r.text


def test_pdf_compression_never_enlarges():
    data=blank_pdf()
    r=upload(data,'small.pdf','pdf','pdf')
    assert r.status_code == 200, r.text
    assert len(r.content)<=len(data)
    assert len(PdfReader(io.BytesIO(r.content)).pages)==1


@pytest.mark.parametrize('category,name,output', [('pdf','bad.pdf','docx'),('document','bad.docx','pdf'),
    ('document','bad.doc','pdf'),('document','bad.rtf','pdf'),('video','bad.mp4','webm'),('audio','bad.mp3','mp3')])
def test_disguised_files(category,name,output):
    r=upload(b'<html>not a file</html>',name,category,output)
    assert r.status_code==422,r.text


def test_external_document_resource_rejected():
    mem=io.BytesIO()
    with zipfile.ZipFile(mem,'w') as z:
        z.writestr('word/document.xml','<document/>')
        z.writestr('word/_rels/document.xml.rels','<Relationships><Relationship TargetMode="External" Type="image" Target="https://example.com/a.png"/></Relationships>')
    r=upload(mem.getvalue(),'linked.docx','document','pdf')
    assert r.status_code==422 and 'external resources' in r.text


def test_guard_headers_and_limits():
    guarded=FastAPI()
    @guarded.post('/api/convert')
    async def endpoint():return {'ok':True}
    guarded.add_middleware(RequestGuards,max_body=100,max_active=1,rate_limit=1)
    c=TestClient(guarded)
    assert c.post('/api/convert',content=b'x'*101).status_code==413
    assert c.post('/api/convert',headers={'sec-fetch-site':'cross-site'}).status_code==403
    r=c.post('/api/convert')
    assert r.status_code==200 and r.headers['x-content-type-options']=='nosniff'
    r=c.post('/api/convert',headers={'X-Forwarded-For':'1.2.3.4'})
    assert r.status_code==429 and r.headers['retry-after']=='60'


def test_chunked_body_bound_and_busy():
    from fastapi import File,UploadFile
    guarded=FastAPI()
    @guarded.post('/api/convert')
    async def endpoint(file:UploadFile=File(...)):return {'ok':True}
    guarded.add_middleware(RequestGuards,max_body=100,max_active=1,rate_limit=0)
    c=TestClient(guarded)
    body=b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="x.txt"\r\n\r\n'+b'a'*300+b'\r\n--boundary--\r\n'
    r=c.post('/api/convert',content=iter([body[:80],body[80:]]),headers={'content-type':'multipart/form-data; boundary=boundary'})
    assert r.status_code==413,r.text
    busy = RequestGuards(guarded, max_body=100, max_active=1, rate_limit=0)
    busy.active=1
    assert TestClient(busy).post('/api/convert').status_code==503


def test_missing_binary_and_safe_error():
    with pytest.raises(ConversionError,match='unavailable'):
        run_command(['/nonexistent/converter'])
    with pytest.raises(ConversionError,match='Could not convert'):
        run_command(['sh','-c','echo /private/secret >&2; exit 1'])


def test_deadline_and_cleanup(monkeypatch):
    monkeypatch.setenv('CONVERSION_TIMEOUT','0.00001')
    before=set(Path('/tmp').glob('convertlab-*'))
    r=upload(png())
    assert r.status_code==422 and 'timed out' in r.text
    assert set(Path('/tmp').glob('convertlab-*')) == before


def test_success_failure_cleanup():
    before=set(Path('/tmp').glob('convertlab-*'))
    assert upload(png()).status_code==200
    assert upload(b'bad').status_code==422
    assert set(Path('/tmp').glob('convertlab-*'))==before


def test_proxy_trust_is_explicit(monkeypatch):
    from starlette.responses import JSONResponse
    async def endpoint(scope,receive,send):
        await JSONResponse({'ok':True})(scope,receive,send)
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS','127.0.0.0/8')
    trusted=TestClient(RequestGuards(endpoint,max_body=100,rate_limit=1),client=('127.0.0.1',1234))
    assert trusted.post('/api/convert',headers={'X-Forwarded-For':'203.0.113.1'}).status_code==200
    assert trusted.post('/api/convert',headers={'X-Forwarded-For':'203.0.113.2'}).status_code==200
    assert trusted.post('/api/convert',headers={'X-Forwarded-For':'203.0.113.1'}).status_code==429


def test_download_cleans_up_after_disconnect(tmp_path):
    from app.main import DownloadResponse
    target=tmp_path/'out.txt';target.write_text('output')
    cleaned=[]
    response=DownloadResponse(target,cleanup=lambda:cleaned.append(True))
    async def disconnected(message):raise ConnectionError('client disconnected')
    with pytest.raises(ConnectionError):
        asyncio.run(response({'type':'http','method':'GET','headers':[], 'asgi':{'spec_version':'2.4'}},None,disconnected))
    assert cleaned==[True]


def test_static_compression_excludes_downloads():
    page=client.get('/',headers={'Accept-Encoding':'gzip'})
    assert page.headers['content-encoding']=='gzip'
    assert 'Start converting' in page.text
    result=upload(png())
    assert result.status_code==200 and 'content-encoding' not in result.headers


def test_exactly_one_file_and_file_size_bound(monkeypatch):
    r=client.post('/api/convert',files=[('file',('a.png',png())),('file',('b.png',png()))],
                  data={'category':'image','output_format':'png'})
    assert r.status_code==422 and 'one file' in r.text
    import app.main as main
    monkeypatch.setattr(main,'MAX_UPLOAD',100)
    r=upload(png())
    assert r.status_code==413
