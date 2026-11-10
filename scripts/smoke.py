"""Real HTTP release gate: run from the test image, against local or public service."""
import argparse
import io
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse
import httpx
from PIL import Image
from docx import Document
from pypdf import PdfReader
from reportlab.pdfgen import canvas

parser=argparse.ArgumentParser()
parser.add_argument('url')
parser.add_argument('--public',action='store_true')
args=parser.parse_args()
if args.public:
    url=urlparse(args.url)
    if url.scheme!='https' or url.hostname in {'localhost','127.0.0.1','host.docker.internal'}:
        parser.error('Public verification requires a real HTTPS hostname.')
with httpx.Client(base_url=args.url.rstrip('/'),timeout=270,follow_redirects=False) as client, tempfile.TemporaryDirectory() as temp:
    assert client.get('/health').json()['status']=='ok'
    homepage=client.get('/');assert homepage.status_code==200 and 'Start converting' in homepage.text
    assert client.get('/api/capabilities').status_code==200
    image=io.BytesIO();Image.new('RGBA',(100,60),'red').save(image,'PNG')
    pdf=io.BytesIO();c=canvas.Canvas(pdf);c.drawString(50,700,'Public converter smoke test');c.save()
    doc=io.BytesIO();d=Document();d.add_paragraph('Public document conversion');d.save(doc)
    media=Path(temp)/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=160x120:r=8:d=1',
                    '-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(media)],check=True)
    cases=[('image','png','jpg',image.getvalue()),('pdf','pdf','docx',pdf.getvalue()),
           ('pdf','pdf','pdf',pdf.getvalue()),('document','docx','pdf',doc.getvalue()),
           ('audio','mp4','mp3',media.read_bytes()),('video','mp4','webm',media.read_bytes())]
    for category,ext,output,content in cases:
        r=client.post('/api/convert',files={'file':(f'smoke.{ext}',content)},data={'category':category,'output_format':output})
        assert r.status_code==200,(category,r.status_code,r.text[:300])
        assert 'attachment' in r.headers['content-disposition'] and int(r.headers['x-converted-bytes'])==len(r.content)
        if output=='jpg':assert Image.open(io.BytesIO(r.content)).size==(100,60)
        elif output=='docx':assert any('smoke test' in p.text for p in Document(io.BytesIO(r.content)).paragraphs)
        elif output=='pdf':assert len(PdfReader(io.BytesIO(r.content)).pages)>0
        else:
            target=Path(temp)/f'output.{output}';target.write_bytes(r.content)
            subprocess.run(['ffmpeg','-v','error','-i',str(target),'-f','null','-'],check=True)
        print(f'PASS {category}: {ext} -> {output}, {len(r.content)} bytes',flush=True)
    invalid=client.post('/api/convert',files={'file':('broken.png',b'bad')},data={'category':'image','output_format':'png'})
    assert invalid.status_code==422 and isinstance(invalid.json()['detail'],str)
    print(f'PASS health, homepage, capabilities, error response; verified {args.url}')
