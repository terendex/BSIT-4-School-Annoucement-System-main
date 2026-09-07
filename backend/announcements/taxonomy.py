"""How announcements are filed: what kind of notice, and who it is for.

Two independent axes, so a reader can ask for "3rd year exam schedules" without
the two lists multiplying into a single unmanageable set of tags:

  category   - what the announcement is about (suspension, holiday, exam, ...)
  year_level - which year it concerns, or ALL when it is for everybody

Both live here rather than on the model so the frontend can fetch the labels
and colours from /api/taxonomy/ and never hardcode a copy that drifts.
"""

# Ordered as they should appear in the filter bar. The tone is a CSS modifier
# suffix (.chip--danger etc.), not a raw colour, so the palette stays in one
# stylesheet.
CATEGORIES = [
    {
        "slug": "suspension",
        "name": "Class suspension",
        "short": "Suspension",
        "tone": "danger",
        "description": "No classes - weather, calamity, or an ordered suspension.",
    },
    {
        "slug": "holiday",
        "name": "Holiday",
        "short": "Holiday",
        "tone": "success",
        "description": "Declared holidays and non-working days.",
    },
    {
        "slug": "exam",
        "name": "Exam schedule",
        "short": "Exam",
        "tone": "info",
        "description": "Prelims, midterms, finals, and exam permits.",
    },
    {
        "slug": "enrollment",
        "name": "Enrollment",
        "short": "Enrollment",
        "tone": "warning",
        "description": "Enrollment, registration, and clearance.",
    },
    {
        "slug": "event",
        "name": "Event",
        "short": "Event",
        "tone": "accent",
        "description": "Seminars, org activities, masses, and school events.",
    },
    {
        "slug": "general",
        "name": "General",
        "short": "General",
        "tone": "neutral",
        "description": "Anything that does not fit the other categories.",
    },
]

DEFAULT_CATEGORY = "general"

YEAR_LEVELS = [
    {"slug": "all", "name": "All year levels", "short": "All years"},
    {"slug": "1", "name": "1st year", "short": "1st yr"},
    {"slug": "2", "name": "2nd year", "short": "2nd yr"},
    {"slug": "3", "name": "3rd year", "short": "3rd yr"},
    {"slug": "4", "name": "4th year", "short": "4th yr"},
]

DEFAULT_YEAR_LEVEL = "all"

CATEGORY_CHOICES = [(item["slug"], item["name"]) for item in CATEGORIES]
CATEGORY_SLUGS = {item["slug"] for item in CATEGORIES}
CATEGORY_BY_SLUG = {item["slug"]: item for item in CATEGORIES}

YEAR_LEVEL_CHOICES = [(item["slug"], item["name"]) for item in YEAR_LEVELS]
YEAR_LEVEL_SLUGS = {item["slug"] for item in YEAR_LEVELS}
YEAR_LEVEL_BY_SLUG = {item["slug"]: item for item in YEAR_LEVELS}


def category_name(slug: str) -> str:
    item = CATEGORY_BY_SLUG.get(slug)
    return item["name"] if item else ""


def year_level_name(slug: str) -> str:
    item = YEAR_LEVEL_BY_SLUG.get(slug)
    return item["name"] if item else ""
