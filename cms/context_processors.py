from core.models import Store

def store_context(request):
    """
    Context processor to make the 'store' object available in all templates
    for authenticated users.
    """
    if request.user.is_authenticated:
        store, _ = Store.objects.get_or_create(user=request.user)
        return {'store': store}
    return {}
