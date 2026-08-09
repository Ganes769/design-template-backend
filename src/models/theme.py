from typing import Optional

from pydantic import BaseModel, Field


class DesignColorToken(BaseModel):
    name: str
    value: str
    role: str


class Effort(BaseModel):
    level: str
    explanation: str


class DesignProfile(BaseModel):
    about: str
    suitedFor: list[str]
    bestChoiceWhen: str
    designPerspective: str
    useCases: list[str]
    interactionModel: str
    implementationNotes: str
    palette: list[DesignColorToken]
    effort: Effort
    considerations: list[str]


class DesignThemeClasses(BaseModel):
    page: str
    decoration: str
    hero: str
    panel: str
    inset: str
    badge: str
    heading: str
    body: str
    muted: str
    metricValue: str
    primaryButton: str
    secondaryButton: str
    input: str
    accent: str


class DesignTheme(BaseModel):
    slug: str = Field(..., min_length=1)
    name: str
    eyebrow: str
    description: str
    designProfile: DesignProfile
    previewVariant: Optional[str] = None
    layout: str
    classes: DesignThemeClasses


class DesignThemeCreate(DesignTheme):
    """POST body for creating a design theme."""
