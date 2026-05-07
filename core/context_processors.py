# core/context_processors.py

def unread_notifications(request):
    """
    Injects unread_count into every template automatically.
    Used by the nav badge.
    """
    if request.user.is_authenticated:
        count = request.user.notifications.filter(
            is_read=False
        ).count()
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}