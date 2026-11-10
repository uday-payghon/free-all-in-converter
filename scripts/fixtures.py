"""Small synthetic files for repeatable browser tests; contains no personal data."""
import sys
import subprocess
from pathlib import Path
from docx import Document
from reportlab.pdfgen import canvas
from pypdf import PdfWriter
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
doc=Document();doc.add_paragraph('Browser document conversion fixture');doc.save(out/'paper.docx')
pdf=canvas.Canvas(str(out/'paper.pdf'));pdf.drawString(50,700,'Browser selectable PDF text');pdf.save()
writer=PdfWriter();writer.add_blank_page(width=100,height=100);writer.write(out/'scan.pdf')
subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=160x120:r=8:d=1',
                '-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(out/'clip.mp4')],check=True)
