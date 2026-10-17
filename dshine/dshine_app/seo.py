from django.conf import settings
from django.http import HttpResponse
from django.utils.html import escape


def seo_context(request):
    public_home = request.path == '/'
    indexable = settings.SITE_INDEXING_ENABLED and public_home
    return {
        'seo_robots': 'index, follow' if indexable else 'noindex, follow',
        'seo_canonical': settings.SITE_URL + '/' if public_home and settings.SITE_URL else '',
    }


class IndexingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not settings.SITE_INDEXING_ENABLED or request.path not in {'/', '/robots.txt', '/sitemap.xml'} or response.status_code >= 400:
            response['X-Robots-Tag'] = 'noindex, follow'
        return response


def robots_txt(request):
    if settings.SITE_INDEXING_ENABLED:
        # Nie blokujemy odczytu stron z noindex: robot musi móc zobaczyć nagłówek.
        content = f'User-agent: *\nAllow: /\nSitemap: {settings.SITE_URL}/sitemap.xml\n'
    else:
        content = 'User-agent: *\nDisallow: /\n'
    return HttpResponse(content, content_type='text/plain; charset=utf-8')


def sitemap_xml(request):
    item = f'<url><loc>{escape(settings.SITE_URL)}/</loc></url>' if settings.SITE_INDEXING_ENABLED else ''
    return HttpResponse('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + item + '</urlset>', content_type='application/xml; charset=utf-8')
