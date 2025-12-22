"""Curated source set presets for Pain Radar.

Presets are pre-configured subreddit bundles targeting specific ICPs.
Users pick a preset (e.g., "Indie SaaS Builders") instead of manually
selecting subreddits.
"""

from typing import TypedDict


class PresetConfig(TypedDict):
    """Configuration for a source set preset."""

    name: str
    description: str
    subreddits: list[str]
    listing: str  # "new", "hot", "top"
    limit: int


PRESETS: dict[str, PresetConfig] = {
    "indie_saas": {
        "name": "Indie SaaS Builders",
        "description": "Solo founders, bootstrappers, micro-SaaS",
        "subreddits": [
            "SideProject",
            "IndieHackers",
            "MicroSaaS",
            "SaaS",
            "startups",
        ],
        "listing": "new",
        "limit": 25,
    },
    "shopify": {
        "name": "Shopify Merchants",
        "description": "E-commerce operators on Shopify",
        "subreddits": [
            "shopify",
            "ecommerce",
            "dropship",
            "Entrepreneur",
            "smallbusiness",
        ],
        "listing": "new",
        "limit": 25,
    },
    "marketing": {
        "name": "Marketing Operators",
        "description": "SEO, PPC, content, growth marketers",
        "subreddits": [
            "marketing",
            "SEO",
            "PPC",
            "growthhacking",
            "content_marketing",
            "digital_marketing",
        ],
        "listing": "new",
        "limit": 25,
    },
    "recruiting": {
        "name": "Recruiting & HR",
        "description": "Talent acquisition, HR tech, people ops",
        "subreddits": [
            "recruiting",
            "humanresources",
            "jobs",
            "careerguidance",
            "recruitinghell",
        ],
        "listing": "new",
        "limit": 25,
    },
    "devtools": {
        "name": "Developers & DevTools",
        "description": "Developer tooling, APIs, infrastructure",
        "subreddits": [
            "programming",
            "webdev",
            "devops",
            "selfhosted",
            "node",
            "golang",
        ],
        "listing": "new",
        "limit": 25,
    },
    "agencies": {
        "name": "Agency Owners",
        "description": "Digital agencies, freelancers, consultants",
        "subreddits": [
            "Entrepreneur",
            "freelance",
            "web_design",
            "digital_marketing",
            "graphic_design",
        ],
        "listing": "new",
        "limit": 25,
    },
    "nocode": {
        "name": "No-Code Builders",
        "description": "No-code/low-code tool users and builders",
        "subreddits": [
            "nocode",
            "Notion",
            "Airtable",
            "zapier",
            "webflow",
        ],
        "listing": "new",
        "limit": 25,
    },
}


def get_preset(key: str) -> PresetConfig | None:
    """Get a preset by key."""
    return PRESETS.get(key)


def list_presets() -> dict[str, PresetConfig]:
    """List all available presets."""
    return PRESETS


def get_preset_keys() -> list[str]:
    """Get list of preset keys."""
    return list(PRESETS.keys())
