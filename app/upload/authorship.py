"""Which listed author is the uploader.

Only authors may post a paper. When the uploader's account name is in the author list,
that entry is theirs. When it is not (for example "L. Torres" on the paper and "Leo
Torres" on the account), the upload form asks which author they are, with a "None of
the above" choice that blocks the upload. The chosen name is stored on the scroll as
uploader_author and decides which author gets the uploader's ORCID, in the Details modal
and on Zenodo.
"""

from typing import Optional

NONE_OF_THE_ABOVE = "__none__"

NOT_AN_AUTHOR = "You can only upload if you are one of the authors."


class UploaderNotFoundError(ValueError):
    """The uploader's account name is not in the author list and they have not chosen one."""


def name_key(name: str) -> str:
    """Normalize a person's name so 'Last, First' and 'first  last' compare equal."""
    if "," in name:
        family, given = name.split(",", 1)
        name = f"{given} {family}"
    return " ".join(name.split()).casefold()


def author_names(authors: str) -> list[str]:
    return [name.strip() for name in (authors or "").split(",") if name.strip()]


def matching_author(authors: str, name: Optional[str]) -> Optional[str]:
    """The entry in `authors` that is the same person as `name`, as written in the list."""
    if not name:
        return None
    key = name_key(name)
    return next((n for n in author_names(authors) if name_key(n) == key), None)


def resolve_uploader_author(authors: str, account_name: Optional[str], choice: str = "") -> str:
    """Return the author entry that belongs to the uploader.

    Raises ValueError with NOT_AN_AUTHOR when they chose "None of the above", and
    UploaderNotFoundError when their account name is not in the list and they have not
    chosen a listed name.
    """
    choice = (choice or "").strip()
    if choice == NONE_OF_THE_ABOVE:
        raise ValueError(NOT_AN_AUTHOR)
    if choice:
        chosen = matching_author(authors, choice)
        if chosen:
            return chosen
    own = matching_author(authors, account_name)
    if own:
        return own
    raise UploaderNotFoundError(
        f'We could not find your name ("{account_name or ""}") in the author list. '
        "Choose which author you are."
    )
