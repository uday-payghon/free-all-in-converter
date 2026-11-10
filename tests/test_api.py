import io
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app

client = TestClient(app)

def image_data():
    b = io.BytesIO()
    Image.new('RGB', (800, 600), '#cc0055').save(b, 'PNG')
    return b.getvalue()

def test_health():
    r = client.get('/health')
    assert r.status_code == 200 and r.json()['status'] == 'ok'

def test_convert_image():
    r = client.post('/api/convert', files={'file': ('test.png', image_data(), 'image/png')},
                    data={'category': 'image', 'output_format': 'jpg', 'target_mb': '0.05'})
    assert r.status_code == 200, r.text
    assert r.content[:2] == b'\xff\xd8'
    assert len(r.content) < .05*1024*1024

def test_reject_invalid_ext():
    r = client.post('/api/convert', files={'file': ('shell.exe', b'bad')},
                    data={'category': 'image', 'output_format': 'png'})
    assert r.status_code == 422

def test_reject_bad_target():
    r = client.post('/api/convert', files={'file': ('test.png', image_data())},
                    data={'category': 'image', 'output_format': 'webp', 'target_mb': '-1'})
    assert r.status_code == 422

def test_image_crop_exact_dimensions():
    r = client.post('/api/convert', files={'file': ('landscape.png', image_data(), 'image/png')},
                    data={'category': 'image', 'output_format': 'webp',
                          'max_width': '320', 'max_height': '320', 'resize_mode': 'cover', 'target_mb': '0.2'})
    assert r.status_code == 200, r.text
    with Image.open(io.BytesIO(r.content)) as img:
        assert img.size == (320, 320)
        assert img.format == 'WEBP'


def test_image_pad_exact_dimensions():
    r = client.post('/api/convert', files={'file': ('landscape.png', image_data(), 'image/png')},
                    data={'category': 'image', 'output_format': 'png',
                          'max_width': '320', 'max_height': '320', 'resize_mode': 'pad'})
    assert r.status_code == 200, r.text
    with Image.open(io.BytesIO(r.content)) as img:
        assert img.size == (320, 320)
        assert img.getpixel((0, 0))[3] == 0


def test_image_preserve_aspect():
    r = client.post('/api/convert', files={'file': ('landscape.png', image_data())},
                    data={'category': 'image', 'output_format': 'jpg',
                          'max_width': '320', 'max_height': '320', 'resize_mode': 'contain'})
    assert r.status_code == 200, r.text
    with Image.open(io.BytesIO(r.content)) as img:
        assert img.size == (320, 240)


def test_image_target_cannot_override_fixed_dimensions():
    # Noise is hard to compress below ~1 KB without changing the requested canvas.
    import random
    random.seed(5)
    raw = random.randbytes(220 * 220 * 3)
    noise = Image.frombytes('RGB', (220, 220), raw)
    memory = io.BytesIO(); noise.save(memory, format='PNG')
    r = client.post('/api/convert', files={'file': ('noise.png', memory.getvalue())},
                    data={'category': 'image', 'output_format': 'png',
                          'max_width': '220', 'max_height': '220', 'resize_mode': 'stretch',
                          'target_mb': '0.001'})
    assert r.status_code == 422, r.text
    assert 'Cannot achieve' in r.json()['detail']


def test_audio_to_mp3_from_video(tmp_path):
    import subprocess
    src = tmp_path / 'sound.mp4'
    result = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
                             '-c:a', 'aac', str(src)], capture_output=True)
    assert result.returncode == 0, result.stderr
    r = client.post('/api/convert', files={'file': ('sound.mp4', src.read_bytes(), 'video/mp4')},
                    data={'category': 'audio', 'output_format': 'mp3', 'target_mb': '0.04'})
    assert r.status_code == 200, r.text
    assert r.content[:3] == b'ID3' or r.content[:2] == b'\xff\xfb'
    assert len(r.content) < 0.04 * 1024 * 1024


def test_frontend_has_three_controls():
    r = client.get('/')
    assert r.status_code == 200
    assert 'id="width"' in r.text and 'id="height"' in r.text
    assert 'id="target"' in r.text and 'id="size-unit"' in r.text

def test_video_to_webm(tmp_path):
    import subprocess
    source = tmp_path / 'clip.mp4'
    result = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                             'testsrc=size=160x120:rate=8:duration=1',
                             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(source)], capture_output=True)
    assert result.returncode == 0, result.stderr
    r = client.post('/api/convert', files={'file': ('clip.mp4', source.read_bytes(), 'video/mp4')},
                    data={'category': 'video', 'output_format': 'webm', 'target_mb': '0.3'})
    assert r.status_code == 200, r.text
    assert r.content[:4] == b'\x1a\x45\xdf\xa3'


def test_document_to_pdf():
    from docx import Document
    memory = io.BytesIO()
    doc = Document()
    doc.add_heading('Uday ConvertLab DOCX test', level=1)
    doc.add_paragraph('Document conversion via LibreOffice headless.')
    doc.save(memory)
    r = client.post('/api/convert', files={'file': ('example.docx', memory.getvalue())},
                    data={'category': 'document', 'output_format': 'pdf'})
    assert r.status_code == 200, r.text
    assert r.content[:4] == b'%PDF'

def test_png_transparency_preserved_under_compression():
    memory = io.BytesIO()
    img = Image.new('RGBA', (250, 250), (200, 10, 50, 0))
    img.save(memory, format='PNG')
    r = client.post('/api/convert', files={'file': ('alpha.png', memory.getvalue())},
                    data={'category': 'image', 'output_format': 'png',
                          'max_width': '250', 'max_height': '250', 'target_mb': '0.005'})
    assert r.status_code == 200, r.text
    with Image.open(io.BytesIO(r.content)) as result:
        assert result.convert('RGBA').getpixel((0, 0))[3] == 0

def test_manual_crop_coordinates_respected():
    memory = io.BytesIO()
    image = Image.new('RGB', (400, 300), '#ffffff')
    from PIL import ImageDraw
    drawer = ImageDraw.Draw(image)
    drawer.rectangle((0, 0, 199, 299), fill='#dd2228')
    image.save(memory, 'PNG')
    r = client.post('/api/convert', files={'file': ('photo.png', memory.getvalue(), 'image/png')}, data={
        'category': 'image', 'output_format': 'png',
        'crop_x': '0', 'crop_y': '0', 'crop_width': '190', 'crop_height': '200'
    })
    assert r.status_code == 200, r.text
    with Image.open(io.BytesIO(r.content)) as result:
        assert result.size == (190, 200)
        assert result.convert('RGB').getpixel((80, 70))[0] > 180
        assert result.convert('RGB').getpixel((80, 70))[1] < 80


def test_invalid_crop_rejected():
    r = client.post('/api/convert', files={'file': ('photo.png', image_data(), 'image/png')}, data={
        'category': 'image', 'output_format': 'png',
        'crop_x': '799', 'crop_y': '0', 'crop_width': '20', 'crop_height': '80'
    })
    assert r.status_code == 422
    assert 'Invalid crop' in r.json()['detail']


def test_pdf_to_editable_word():
    from reportlab.pdfgen import canvas
    from docx import Document
    memory = io.BytesIO()
    pdf = canvas.Canvas(memory)
    pdf.drawString(80, 720, 'Free All-in Converter test paragraph')
    pdf.save()
    r = client.post('/api/convert', files={'file': ('paper.pdf', memory.getvalue(), 'application/pdf')}, data={
        'category': 'pdf', 'output_format': 'docx'
    })
    assert r.status_code == 200, r.text
    result = Document(io.BytesIO(r.content))
    assert any('Free All-in Converter' in p.text for p in result.paragraphs)


def test_public_site_has_category_picker_and_no_login_requirement():
    page = client.get('/').text
    assert 'id="category-modal"' in page
    assert 'id="crop-modal"' in page
    assert 'data-mode="pdf"' in page
    assert 'No login' in page


def test_tiny_icon_dimensions_allowed():
    r = client.post('/api/convert', files={'file': ('icon.png', image_data(), 'image/png')}, data={
        'category': 'image', 'output_format': 'png',
        'max_width': '32', 'max_height': '32', 'resize_mode': 'cover'
    })
    assert r.status_code == 200, r.text
    with Image.open(io.BytesIO(r.content)) as result:
        assert result.size == (32, 32)
