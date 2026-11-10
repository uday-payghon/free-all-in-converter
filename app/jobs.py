import asyncio
import json
import os
import signal
import sys
from .processor import ConversionError


async def run_job(job):
    process = await asyncio.create_subprocess_exec(
        sys.executable, '-m', 'app.worker', stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
        env={**os.environ, 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'})
    try:
        output, _ = await asyncio.wait_for(
            process.communicate(json.dumps(job).encode()),
            timeout=float(os.getenv('CONVERSION_TIMEOUT', '240')))
        try:
            result = json.loads(output)
        except (ValueError, UnicodeDecodeError):
            raise ConversionError('Conversion exceeded available resources. Try a smaller file.')
        if 'error' in result:
            raise ConversionError(result['error'])
        if process.returncode or not result.get('ok'):
            raise ConversionError('Conversion failed. Try a smaller file.')
    except asyncio.TimeoutError as exc:
        raise ConversionError('Conversion timed out. Try a smaller file.') from exc
    finally:
        # Kill the entire job group, including any surviving native converter children.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()
