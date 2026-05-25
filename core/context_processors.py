from .navigation import chemin_avec_next


def navigation(request):
    chemin = request.get_full_path() if request else ""
    return {
        "chemin_actuel": chemin,
    }
