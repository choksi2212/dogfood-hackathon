"""Widget endpoints: /widget.js (script shim) and /api/widget/gallery (JSON)."""

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from apps.events.models import Event
from apps.submissions.models import Submission

WIDGET_JS = """(function() {
  var cfg = window.DOGFOOD_WIDGET || {};
  var api = cfg.api || '/api/widget/gallery';
  var eventSlug = cfg.event || '';
  var target = cfg.target || document.currentScript.parentNode;

  function render(items) {
    var ul = document.createElement('ul');
    ul.style.listStyle = 'none';
    items.forEach(function(it) {
      var li = document.createElement('li');
      li.innerHTML = '<strong>' + it.name + '</strong> — ' + it.tagline;
      ul.appendChild(li);
    });
    target.appendChild(ul);
  }

  var url = api + (eventSlug ? '?event=' + encodeURIComponent(eventSlug) : '');
  fetch(url, { credentials: 'omit' })
    .then(function(r) { return r.json(); })
    .then(function(d) { render(d.items || []); })
    .catch(function(e) { console.error('DOGFOOD widget error:', e); });
})();
"""


@require_GET
@cache_control(public=True, max_age=3600)
def widget_js(request):
    """Static script — cacheable for an hour. Embedders can re-host it."""
    resp = HttpResponse(WIDGET_JS, content_type="application/javascript")
    resp["Access-Control-Allow-Origin"] = "*"
    return resp


@require_GET
@csrf_exempt
def widget_gallery(request):
    from django.core.cache import cache

    event_slug = request.GET.get("event") or "sample-hack-2026"
    cache_key = f"widget_gallery:{event_slug}"
    cached = cache.get(cache_key)
    if cached is not None:
        resp = JsonResponse(cached)
        resp["Access-Control-Allow-Origin"] = "*"
        resp["Cache-Control"] = "public, max-age=60"
        resp["X-Cache"] = "HIT"
        return resp

    try:
        event = Event.objects.get(slug=event_slug)
    except Event.DoesNotExist:
        return JsonResponse({"items": []})

    qs = (
        Submission.objects.filter(event=event, status="submitted")
        .select_related("track")
        .order_by("track__order", "name")
    )
    items = [
        {
            "id": str(s.id),
            "name": s.name,
            "tagline": s.tagline,
            "track_slug": s.track.slug,
        }
        for s in qs[:24]
    ]
    body = {"items": items, "event": event_slug}
    cache.set(cache_key, body, timeout=60)
    resp = JsonResponse(body)
    resp["Access-Control-Allow-Origin"] = "*"
    resp["Cache-Control"] = "public, max-age=60"
    resp["X-Cache"] = "MISS"
    return resp
