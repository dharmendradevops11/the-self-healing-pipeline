"""A small app with one deliberate bug, for experimenting with the pipeline."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Profile:
    name: str


@dataclass
class User:
    id: str
    profile: Optional[Profile] = None


@dataclass
class Session:
    user: User


def get_display_name(session: Session) -> str:
    # First OAuth login: new users have no profile yet. This line crashes for them.
    return session.user.profile.name.strip()  # type: ignore[union-attr]


def greet(session: Session) -> str:
    return f"Welcome back, {get_display_name(session)}!"
