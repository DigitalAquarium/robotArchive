import django

def _404(request):
    return django.views.defaults.page_not_found(request, None)

def _500(request):
    return django.views.defaults.server_error(request)