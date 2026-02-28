from connections.models import Connection


def connections(request):
    if not request.user.is_authenticated:
        return {"connections": []}
    return {"connections": Connection.objects.all()}
