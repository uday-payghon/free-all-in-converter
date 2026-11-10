"""Real encoders and parsers, not mocked success responses."""
import io
import json
import subprocess
import pytest
from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from pypdf import PdfReader
from .test_edges import upload


def command(args):
    r=subprocess.run(args,capture_output=True,timeout=60)
    assert r.returncode==0,r.stderr.decode(errors='replace')


@pytest.fixture(scope='module')
def media(tmp_path_factory):
    directory=tmp_path_factory.mktemp('media')
    source=directory/'source.mp4'
    command(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc=size=162x122:rate=8:duration=2',
             '-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(source)])
    return directory,source


@pytest.mark.parametrize('ext',['mp4','webm','mov','mkv','avi'])
@pytest.mark.parametrize('output',['mp4','webm'])
def test_video_inputs_outputs(media,tmp_path,ext,output):
    directory,base=media;source=tmp_path/f'input.{ext}'
    codecs=['-c:v','libvpx-vp9','-c:a','libopus'] if ext=='webm' else ['-c:v','mpeg4','-c:a','mp3'] if ext=='avi' else ['-c','copy']
    command(['ffmpeg','-v','error','-y','-i',str(base),*codecs,str(source)])
    r=upload(source.read_bytes(),source.name,'video',output,max_width=101,target_mb='0.2')
    assert r.status_code==200,r.text
    result=tmp_path/f'output.{output}';result.write_bytes(r.content)
    command(['ffmpeg','-v','error','-i',str(result),'-f','null','-'])
    probe=subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(result)],capture_output=True,text=True,check=True)
    video=next(s for s in json.loads(probe.stdout)['streams'] if s['codec_type']=='video')
    assert video['width']<=101 and video['width']%2==0
    assert len(r.content)<=.2*1024*1024


@pytest.mark.parametrize('ext',['mp3','wav','m4a','ogg','flac','aac','wma','mp4','webm','mov','mkv','avi'])
def test_audio_inputs(media,tmp_path,ext):
    _,base=media;source=tmp_path/f'audio.{ext}'
    options=['-vn']
    if ext in {'mp4','mov','mkv','avi'}:options=[]
    if ext=='webm':options=['-vn','-c:a','libopus']
    command(['ffmpeg','-v','error','-y','-i',str(base),*options,str(source)])
    r=upload(source.read_bytes(),source.name,'audio','mp3',target_mb='0.05')
    assert r.status_code==200,r.text
    result=tmp_path/'out.mp3';result.write_bytes(r.content)
    command(['ffmpeg','-v','error','-i',str(result),'-f','null','-'])


@pytest.mark.parametrize('output',['mp3','wav','m4a','ogg'])
def test_audio_outputs(media,tmp_path,output):
    _,source=media
    r=upload(source.read_bytes(),'input.mp4','audio',output)
    assert r.status_code==200,r.text
    result=tmp_path/f'out.{output}';result.write_bytes(r.content)
    command(['ffmpeg','-v','error','-i',str(result),'-f','null','-'])


def test_media_impossible_and_missing_tracks(media,tmp_path):
    _,source=media
    for category,output in [('audio','mp3'),('audio','wav'),('video','mp4')]:
        r=upload(source.read_bytes(),'input.mp4',category,output,target_mb=1/1024)
        assert r.status_code==422,r.text
    silent=tmp_path/'silent.mp4'
    command(['ffmpeg','-v','error','-i',str(source),'-an','-c:v','copy',str(silent)])
    r=upload(silent.read_bytes(),'silent.mp4','audio','mp3')
    assert r.status_code==422 and 'no audio' in r.text
    audio=tmp_path/'sound.mp4'
    command(['ffmpeg','-v','error','-i',str(source),'-vn','-c:a','copy',str(audio)])
    r=upload(audio.read_bytes(),'sound.mp4','video','mp4')
    assert r.status_code==422 and 'no video' in r.text


@pytest.fixture(scope='module')
def documents(tmp_path_factory):
    d=tmp_path_factory.mktemp('documents')
    doc=Document();doc.add_paragraph('Converter document matrix');doc.save(d/'word.docx')
    book=Workbook();book.active['A1']='Converter spreadsheet matrix';book.save(d/'sheet.xlsx')
    deck=Presentation();slide=deck.slides.add_slide(deck.slide_layouts[0]);slide.shapes.title.text='Converter presentation matrix';deck.save(d/'slides.pptx')
    (d/'text.txt').write_text('Converter plain text matrix')
    for source,exts in [('word.docx',['doc','rtf','odt']),('sheet.xlsx',['xls','ods']),('slides.pptx',['ppt','odp'])]:
        for ext in exts:
            command(['libreoffice',f'-env:UserInstallation={(d/"profile").as_uri()}','--headless','--convert-to',ext,'--outdir',str(d),str(d/source)])
            assert (d/(source.split('.')[0]+'.'+ext)).exists()
    return d


@pytest.mark.parametrize('filename',['word.doc','word.docx','word.rtf','word.odt','sheet.xls','sheet.xlsx','sheet.ods','slides.ppt','slides.pptx','slides.odp','text.txt'])
def test_document_input_matrix(documents,filename):
    r=upload((documents/filename).read_bytes(),filename,'document','pdf')
    assert r.status_code==200,r.text
    reader=PdfReader(io.BytesIO(r.content))
    assert any('Converter' in (p.extract_text() or '') for p in reader.pages)
