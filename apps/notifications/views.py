from core.http import redirect
from core.views import login_required, render

from . import models


@login_required
def notification_list(request):
    rows = models.for_user(request.user["id"])
    return render(request, "notifications/list.html", {"notifications": rows})


@login_required
def mark_read(request, id):
    models.mark_read(id, request.user["id"])
    link = request.POST("link")
    return redirect(link if link and link.startswith("/") else "/notifications")


@login_required
def mark_all(request):
    models.mark_all_read(request.user["id"])
    return redirect("/notifications")
