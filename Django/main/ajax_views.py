from django.http import JsonResponse

from .forms import *


def get_location(request):
    id = request.GET.get("id") or ""
    try:
        id = int(id)
        l = Location.objects.get(id=id)
        return JsonResponse({"name": l.name, "latitude": l.latitude, "longitude": l.longitude}, status=200)
    except e:
        return JsonResponse({"id": id}, status=400)
