"""Single-process prototype guards; forwarded IPs require explicit trusted proxy networks."""
import asyncio
import ipaddress
import hashlib
import os
import time
from collections import OrderedDict
from starlette.responses import JSONResponse


class RequestGuards:
    def __init__(self, app, max_body, max_active=3, rate_limit=12):
        self.app, self.max_body = app, max_body
        self.max_active, self.rate_limit = max_active, rate_limit
        self.active = 0
        self.clients = OrderedDict()
        self.salt = os.urandom(32)
        self.trusted_proxies = [ipaddress.ip_network(c.strip()) for c in os.getenv('TRUSTED_PROXY_CIDRS', '').split(',') if c.strip()]

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        async def secured_send(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers += [(b'x-content-type-options', b'nosniff'),
                            (b'x-frame-options', b'DENY'),
                            (b'referrer-policy', b'no-referrer'),
                            (b'permissions-policy', b'camera=(), microphone=(), geolocation=()'),
                            (b'content-security-policy', b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"),
                            (b'cache-control', b'no-store' if scope['path'].startswith('/api/') else b'no-cache')]
                message = {**message, 'headers': headers}
            await send(message)
        if scope['path'] != '/api/convert' or scope['method'] != 'POST':
            return await self.app(scope, receive, secured_send)
        async def reject(code, detail, retry=False):
            await JSONResponse({'detail': detail}, status_code=code,
                               headers={'Retry-After': '60'} if retry else None)(scope, receive, secured_send)
        headers = dict(scope['headers'])
        if headers.get(b'sec-fetch-site') == b'cross-site':
            return await reject(403, 'Please upload files from this website.')
        try:
            if int(headers.get(b'content-length', b'0')) > self.max_body:
                return await reject(413, 'Upload is too large. Choose a smaller file.')
        except ValueError:
            return await reject(400, 'Invalid request length.')
        now = time.monotonic()
        peer = str((scope.get('client') or ('unknown',))[0])
        try:
            if any(ipaddress.ip_address(peer) in network for network in self.trusted_proxies):
                chain = headers.get(b'x-forwarded-for', b'').decode('ascii').split(',')
                for hop in reversed(chain):
                    address = ipaddress.ip_address(hop.strip())
                    peer = str(address)
                    if not any(address in network for network in self.trusted_proxies):
                        break
        except (ValueError, UnicodeDecodeError):
            peer = str((scope.get('client') or ('unknown',))[0])
        key = hashlib.sha256(self.salt + peer.encode()).digest()
        count, start = self.clients.pop(key, (0, now))
        if now - start >= 60:
            count, start = 0, now
        self.clients[key] = (count + 1, start)
        while len(self.clients) > 4096:
            self.clients.popitem(last=False)
        if self.rate_limit and count >= self.rate_limit:
            return await reject(429, 'Too many conversions. Please wait a minute and try again.', True)
        if self.active >= self.max_active:
            return await reject(503, 'The converter is busy. Please try again shortly.', True)
        self.active += 1
        total, rejected_status, sent_limit = 0, None, False
        upload_started = time.monotonic()
        body_complete = False
        async def limited_receive():
            nonlocal total, rejected_status, body_complete
            if body_complete:
                return await receive()
            from starlette.formparsers import MultiPartException
            try:
                remaining = max(0.001, min(30, 120 - (time.monotonic() - upload_started)))
                message = await asyncio.wait_for(receive(), remaining)
            except asyncio.TimeoutError:
                rejected_status = 408
                raise MultiPartException('Upload timed out.')
            if message['type'] == 'http.request' and not message.get('more_body', False):
                body_complete = True
            total += len(message.get('body', b''))
            if total > self.max_body:
                rejected_status = 413
                # The multipart parser cleans up its temporary files on this error.
                raise MultiPartException('Upload is too large.')
            return message
        async def limited_send(message):
            nonlocal sent_limit
            if rejected_status:
                if not sent_limit:
                    sent_limit = True
                    await reject(rejected_status, 'Upload timed out. Please try again.' if rejected_status == 408 else 'Upload is too large. Choose a smaller file.')
                return
            await secured_send(message)
        try:
            await self.app(scope, limited_receive, limited_send)
        finally:
            self.active -= 1
