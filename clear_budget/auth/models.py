"""Auth domain models."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class User:
    """Represents an authenticated user."""

    id: int
    username: str
    is_admin: bool
    is_read_only: bool = False
