def notifications(request):
    return {"unread_count": request.user.notifications.filter(read_at__isnull=True).count() if request.user.is_authenticated else 0}
