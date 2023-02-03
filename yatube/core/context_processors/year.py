from datetime import datetime


def year(request):
    """Добавляет переменную с текущим годом."""
    currentYear = datetime.now().year
    return {
        'year': currentYear
    }
