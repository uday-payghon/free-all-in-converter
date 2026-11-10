from html import escape
from fastapi.testclient import TestClient
from app.main import app
from app.seo import TOOLS, ORIGIN

client = TestClient(app)

def test_all_tools_have_distinct_indexable_pages():
    for slug, (title, _category, _description, _instructions, _format) in TOOLS.items():
        response = client.get('/tools/' + slug)
        assert response.status_code == 200, slug
        assert '<h1>' + escape(title) + '</h1>' in response.text
        assert f'<link rel="canonical" href="{ORIGIN}/tools/{slug}">' in response.text
        assert 'application/ld+json' in response.text
        assert 'Start converting' in response.text

def test_unknown_tool_is_404():
    response = client.get('/tools/not-a-real-tool')
    assert response.status_code == 404

def test_sitemap_links_and_xml_content_type():
    response = client.get('/sitemap.xml')
    assert response.status_code == 200
    assert 'xml' in response.headers['content-type']
    assert '<urlset' in response.text
    for slug in TOOLS:
        assert f'{ORIGIN}/tools/{slug}' in response.text

def test_robots_references_sitemap_and_blocks_api_crawl():
    response = client.get('/robots.txt')
    assert response.status_code == 200
    assert f'Sitemap: {ORIGIN}/sitemap.xml' in response.text
    assert 'Disallow: /api/' in response.text

def test_homepage_theme_metadata_sponsor_clarity():
    response = client.get('/')
    assert response.status_code == 200
    assert 'id="theme-toggle"' in response.text
    assert 'id="success-toast"' in response.text
    assert 'Mr. Uday Payghon' in response.text
    assert 'No partner endorsement is claimed' in response.text
    assert '100K+' not in response.text
    assert 'Google Partner' not in response.text
