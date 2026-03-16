def is_listing_url(url):

    if not url:
        return False

    forbidden = [
        "/ville-",
        "/quartier-",
        "/canton-",
        "/region-",
        "#"
    ]

    for f in forbidden:
        if f in url:
            return False

    return True
