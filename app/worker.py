"""One disposable process per conversion, including Pillow and PDF parsing."""
import json
import os
import sys
from pathlib import Path


def main():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (240, 245))
    resource.setrlimit(resource.RLIMIT_FSIZE, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    if sys.platform == 'linux':
        memory = int(os.getenv('WORKER_MEMORY_MB', '1024')) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    from .processor import (ConversionError, validate_content, convert_image, convert_video,
                            convert_audio, compress_pdf, pdf_to_docx, convert_document)
    job = json.loads(sys.stdin.read())
    source, destination = Path(job['source']), Path(job['destination'])
    category, fmt, target = job['category'], job['fmt'], job['target']
    try:
        validate_content(source, category)
        if category == 'image':
            convert_image(source, destination, fmt, target, job['width'], job['height'], job['resize'], job['crop'])
        elif category == 'video':
            convert_video(source, destination, fmt, target, job['width'])
        elif category == 'audio':
            convert_audio(source, destination, fmt, target)
        elif category == 'pdf':
            if fmt == 'docx':
                pdf_to_docx(source, destination)
            else:
                compress_pdf(source, destination, target)
        else:
            convert_document(source, destination.parent, destination.stem)
            if target and destination.stat().st_size > target:
                compressed = destination.with_name('compressed.pdf')
                compress_pdf(destination, compressed, target)
                compressed.replace(destination)
        if not destination.exists() or not destination.stat().st_size:
            raise ConversionError('No output was produced. Check the file and try again.')
        if target and destination.stat().st_size > target:
            raise ConversionError('The output exceeds your size limit. Increase or remove the limit.')
        print(json.dumps({'ok': True}))
    except ConversionError as exc:
        print(json.dumps({'error': str(exc)}))
    except MemoryError:
        print(json.dumps({'error': 'This file needs too much memory. Try a smaller file or lower dimensions.'}))
    except Exception:
        print(json.dumps({'error': 'Could not convert this file. It may be damaged or unsupported.'}))


if __name__ == '__main__':
    main()
