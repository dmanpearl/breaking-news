"""
Redoc documentation view for the Breaking News API.

Ninja only auto-registers one docs URL (Swagger by default). This view
serves Redoc via CDN — no collectstatic dependency, works in dev and
production identically.
"""

from django.http import HttpResponse


def redoc_view(request):
    """Render the Redoc API documentation page (CDN-based, no static deps)."""
    openapi_url = "/api/v1/openapi.json"
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Breaking News API</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
        body {{ margin: 0; padding: 0; }}
    </style>
</head>
<body>
    <div id="redoc-container"></div>
    <script src="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"></script>
    <script>
        Redoc.init(
            '{openapi_url}',
            {{
                scrollYOffset: 0,
                hideDownloadButton: false,
                expandResponses: "200,201",
            }},
            document.getElementById('redoc-container')
        );
    </script>
</body>
</html>"""
    return HttpResponse(html)
