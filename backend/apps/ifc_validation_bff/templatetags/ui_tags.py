from django import template
from django.utils import timezone

register = template.Library()


@register.inclusion_tag("ui/icon.html")
def material_icon(name):
    return {"name": name}


@register.filter
def check_label(status):
    return {"v": "Valid", "i": "Invalid", "w": "Warning", "n": "Not validated", "p": "Pending", "-": "N/A"}[status]


@register.filter
def check_icon(status):
    return {"v": "CheckCircleIcon", "i": "ErrorIcon", "w": "WarningIcon", "p": "HourglassBottomIcon", "n": "BrowserNotSupportedIcon", "-": "BlockIcon"}[status]


@register.filter
def dashboard_date(created, now=None):
    """Keep the dashboard's single-unit relative dates and eight-day cutoff."""
    seconds = ((now or timezone.now()) - created).total_seconds()
    if seconds > 8 * 86400:
        return created.strftime("%Y-%m-%d %H:%M:%S")
    for divisor, unit in ((7 * 86400, "week"), (86400, "day"), (3600, "hour"), (60, "minute"), (1, "second")):
        if seconds > divisor:
            amount = int(seconds // divisor)
            return f"{amount} {unit}{'' if amount == 1 else 's'} ago"
    return ""
