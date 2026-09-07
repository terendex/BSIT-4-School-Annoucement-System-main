"""The Facebook pages announcements are re-posted from.

These are the pages the admin watches. Automated reading of a page's posts is
only possible for pages the app has been granted a Page access token for, so an
announcement records where it came from rather than fetching it: the admin
opens the post, copies the caption and poster image into the editor, and the
source URL is kept so readers can jump to the original.
"""

SOURCE_PAGES = [
    {
        "slug": "slc1964",
        "name": "Saint Louis College",
        "url": "https://www.facebook.com/slc1964",
    },
    {
        "slug": "SLCCSC",
        "name": "SLC Central Student Council",
        "url": "https://www.facebook.com/SLCCSC",
    },
    {
        "slug": "SLCstudentHelpDesk",
        "name": "SLC Student Help Desk",
        "url": "https://www.facebook.com/SLCstudentHelpDesk",
    },
    {
        "slug": "slcRegistrar",
        "name": "SLC Registrar",
        "url": "https://www.facebook.com/slcRegistrar",
    },
    {
        "slug": "slccasteitcrim",
        "name": "SLC CAS-TE-IT-CRIM",
        "url": "https://www.facebook.com/slccasteitcrim",
    },
    {
        "slug": "sits.slclu",
        "name": "Society of Information Technology Students - SLC La Union",
        "url": "https://www.facebook.com/sits.slclu",
    },
]

SOURCE_PAGE_CHOICES = [(page["slug"], page["name"]) for page in SOURCE_PAGES]
SOURCE_PAGE_SLUGS = {page["slug"] for page in SOURCE_PAGES}
SOURCE_PAGE_BY_SLUG = {page["slug"]: page for page in SOURCE_PAGES}


def page_name(slug: str) -> str:
    page = SOURCE_PAGE_BY_SLUG.get(slug)
    return page["name"] if page else ""
