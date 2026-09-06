"""Read complete canonical inputs for calculations and frozen simulations."""
def all_pages(loader, *args, page_size=500, **filters):
    result, offset = [], 0
    while True:
        page = loader(*args, limit=page_size, offset=offset, **filters)
        result.extend(page)
        if len(page) < page_size:
            return result
        offset += len(page)
