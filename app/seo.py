"""Search-friendly HTML pages for genuine, supported conversion routes.

Canonical origin must change only after a verified custom-domain cutover.
"""
from html import escape
from urllib.parse import quote
import json

ORIGIN = "https://free-all-in-converter.onrender.com"
TOOLS = {
    "resize-image-online": ("Resize Image Online — Free JPG, PNG & WEBP Resizer", "image", "Resize images online by pixel width and height, preserve their aspect ratio, and optionally set a maximum size in KB or MB.", "Keep the image format you prefer, choose width and height, and preview the original before converting.", "jpg"),
    "compress-image-to-200kb": ("Compress Image to 200 KB Online — Free Image Size Reducer", "image", "Compress a JPG, PNG or WEBP image to 200 KB or less when technically achievable, without signing up.", "Choose the Image category, upload a picture, enter 200 KB in Maximum output file size, and convert. Very small limits can be impossible at large dimensions.", "jpg"),
    "jpg-to-png": ("JPG to PNG Converter — Free Online Image Converter", "image", "Convert JPG images to PNG online, optionally crop and resize, and download the resulting image for free.", "Choose Image, upload a JPG file, select PNG as the output, and optionally specify dimensions or a maximum KB limit.", "png"),
    "png-to-jpg": ("PNG to JPG Converter — Free Online Image Converter", "image", "Convert PNG images to JPG online with adjustable width, height, crop and optional maximum file size.", "Choose Image, upload PNG, choose JPG, and select the dimensions and maximum file size you need. Transparent areas are flattened for JPG output.", "jpg"),
    "jpg-to-webp": ("JPG to WEBP Converter — Free Image Converter", "image", "Convert JPG pictures into WEBP, optionally set a size ceiling and image dimensions, and download directly.", "Choose Image, upload a JPG image and select WEBP as the destination format.", "webp"),
    "webp-to-jpg": ("WEBP to JPG Converter — Free Image Converter", "image", "Convert WEBP images to JPG without registration. Crop, resize, and set a maximum output file size.", "Choose Image, upload WEBP and select JPG. Transparency is converted to a solid background for JPG.", "jpg"),
    "pdf-to-word": ("PDF to Word Converter — Free Editable DOCX Text", "pdf", "Convert text-based PDFs to editable Word DOCX documents for free. No account or sign-up required.", "Choose PDF tools, upload a PDF containing selectable text, and choose DOCX. Scanned PDFs and complex-layout reconstruction are not yet supported.", "docx"),
    "word-to-pdf": ("Word to PDF Converter — Free DOCX to PDF", "document", "Convert your Word DOCX or DOC files into PDFs online with a direct download and no account.", "Choose Document, upload a Word file, and convert to PDF. Fonts and advanced layouts may vary.", "pdf"),
    "mp4-to-mp3": ("MP4 to MP3 Converter — Free Audio Extraction", "audio", "Extract MP3 audio from your own MP4 video uploads for free, with an optional maximum output size.", "Choose Audio, upload an MP4 containing audio, and select MP3. Downloading from streaming services is not supported.", "mp3"),
    "compress-pdf": ("Compress PDF Online — Free PDF Size Reduction", "pdf", "Reduce a PDF file size online with best-effort compression and no registration.", "Choose PDF tools, upload a PDF and select PDF output. Some already compressed PDFs cannot be made smaller.", "pdf"),
}

def tool_page(slug):
    title, category, description, instructions, fmt = TOOLS[slug]
    url = f"{ORIGIN}/tools/{quote(slug)}"
    metadata = json.dumps({"@context":"https://schema.org","@type":"WebApplication",
                           "name":title,"url":url,"applicationCategory":"UtilitiesApplication",
                           "operatingSystem":"Any","isAccessibleForFree":True,
                           "description":description},ensure_ascii=True).replace("<", "\\u003c")
    title, description, instructions = map(escape, (title, description, instructions))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="robots" content="index,follow,max-image-preview:large">
<meta name="theme-color" content="#ffffff"><meta name="description" content="{description}">
<link rel="canonical" href="{url}"><meta property="og:type" content="website">
<meta property="og:title" content="{title}"><meta property="og:description" content="{description}">
<meta property="og:url" content="{url}"><meta name="twitter:card" content="summary">
<title>{title} | Free All-in Converter</title><script type="application/ld+json">{metadata}</script>
<link rel="icon" href="/static/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/static/style.css">
<script>try{{const t=localStorage.getItem("converter-theme");document.documentElement.dataset.theme=t==="dark"||t==="light"?t:(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light")}}catch(e){{document.documentElement.dataset.theme="light"}}</script>
</head><body><header class="site-header"><div class="header-inner page-width"><a class="brand" href="/">free<span class="brand-emphasis">convert</span></a><nav class="desktop-nav" aria-label="Primary"><a href="/#tools">All tools</a><a href="/#questions">FAQ</a></nav><a class="nav-cta" href="/?tool={category}&format={fmt}#workspace">Open converter ↗</a></div></header>
<main class="seo-tool-page page-width"><span class="section-label">FREE ONLINE CONVERTER</span>
<h1>{title}</h1><p class="seo-lead">{description}</p><section class="seo-tool-card"><h2>How to use this converter</h2><p>{instructions}</p><a class="primary-btn" href="/?tool={category}&format={fmt}#workspace">Start converting ↗</a><p class="seo-tool-note">No registration, no watermark added, and direct download. Output-size targets are maximum limits, not guaranteed exact byte counts.</p></section>
<section class="seo-more-tools"><h2>More conversion tools</h2><div class="discover-links">{''.join(f'<a href="/tools/{other}">{escape(info[0])} ↗</a>' for other,info in TOOLS.items() if other != slug)}</div></section></main>
<footer class="site-footer"><div class="page-width footer-inner"><a href="/" class="footer-brand">Free All-in Converter</a><span>Developed by <strong>Mr. Uday Payghon</strong> · <a href="https://www.linkedin.com/in/cyber-uday/" rel="noopener noreferrer">Contact developer</a></span></div></footer>
</body></html>"""

def sitemap():
    entries = [f"{ORIGIN}/"] + [f"{ORIGIN}/tools/{slug}" for slug in TOOLS]
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f"<url><loc>{escape(uri)}</loc></url>\n" for uri in entries) + '</urlset>\n'

def robots():
    return f"User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: {ORIGIN}/sitemap.xml\n"
