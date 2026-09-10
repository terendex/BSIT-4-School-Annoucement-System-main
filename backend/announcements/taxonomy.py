"""How announcements are filed: what kind of notice, and who it is for.

Three independent axes, so a reader can ask for "3rd year exam schedules"
without the lists multiplying into a single unmanageable set of tags:

  category   - what the announcement is about (suspension, holiday, exam, ...)
  year_level - which year it concerns, or ALL when it is for everybody
  section    - which section within that year, or ALL for every section

Year and section are separate because most notices are for a whole year, and
the ones that are not are for one section of it - 4A is "4th year" plus
"section A", not a fourteenth entry in a combined list.

All three live here rather than on the model so the frontend can fetch the
labels from /api/taxonomy/ and never hardcode a copy that drifts.
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

# Sections within a year. A post for "all" sections stays visible whichever
# section a reader filters to, exactly as a post for "all" years does.
SECTIONS = [
    {"slug": "all", "name": "All sections", "short": "All sections"},
    {"slug": "a", "name": "Section A", "short": "A"},
    {"slug": "b", "name": "Section B", "short": "B"},
    {"slug": "c", "name": "Section C", "short": "C"},
    {"slug": "d", "name": "Section D", "short": "D"},
    {"slug": "e", "name": "Section E", "short": "E"},
]

DEFAULT_SECTION = "all"

CATEGORY_CHOICES = [(item["slug"], item["name"]) for item in CATEGORIES]
CATEGORY_SLUGS = {item["slug"] for item in CATEGORIES}
CATEGORY_BY_SLUG = {item["slug"]: item for item in CATEGORIES}

YEAR_LEVEL_CHOICES = [(item["slug"], item["name"]) for item in YEAR_LEVELS]
YEAR_LEVEL_SLUGS = {item["slug"] for item in YEAR_LEVELS}
YEAR_LEVEL_BY_SLUG = {item["slug"]: item for item in YEAR_LEVELS}

SECTION_CHOICES = [(item["slug"], item["name"]) for item in SECTIONS]
SECTION_SLUGS = {item["slug"] for item in SECTIONS}
SECTION_BY_SLUG = {item["slug"]: item for item in SECTIONS}


def category_name(slug: str) -> str:
    item = CATEGORY_BY_SLUG.get(slug)
    return item["name"] if item else ""


def year_level_name(slug: str) -> str:
    item = YEAR_LEVEL_BY_SLUG.get(slug)
    return item["name"] if item else ""


def section_name(slug: str) -> str:
    item = SECTION_BY_SLUG.get(slug)
    return item["name"] if item else ""


def audience_name(year_level: str, section: str) -> str:
    """Who a post is for, as one label: "4A", "4th year", or "Section A".

    Returns an empty string when it is for everybody, so a card leaves the tag
    off rather than reading "All year levels, all sections".
    """
    year = YEAR_LEVEL_BY_SLUG.get(year_level)
    part = SECTION_BY_SLUG.get(section)
    has_year = year is not None and year_level != DEFAULT_YEAR_LEVEL
    has_section = part is not None and section != DEFAULT_SECTION

    if has_year and has_section:
        # The year slugs are the bare digits, so this reads "4A" - what
        # everybody actually calls it - rather than "4th year, Section A".
        return f"{year_level}{part['short']}"
    if has_year:
        return year["name"]
    if has_section:
        return part["name"]
    return ""
