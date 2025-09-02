import gettext
from string import Template

from electro.settings import settings

translations = {
    "en": gettext.translation("messages", localedir=settings.LOCALES_PATH, languages=["en"]),
    "fr": gettext.translation("messages", localedir=settings.LOCALES_PATH, languages=["fr"]),
}


class TemplatedString(str, Template):
    """A string that can be used both as a string and as a template."""

    def __repr__(self) -> str:
        """Return a representation of the string."""
        return f"TemplatedString({super().__repr__()})"


class TranslatedString:
    def __init__(self, key: str):
        self.key = key
        self.substitutions = {}

    def __repr__(self) -> str:
        """Return a representation of the string."""
        return f"TranslatedString({self.key!r})"

    def get_identifiers(self, locale: str) -> list[str]:
        """Get the identifiers used in the translation string."""
        lang = translations[locale if locale in translations else "en"]
        translated_message = TemplatedString(lang.gettext(self.key))
        return translated_message.get_identifiers()

    def safe_substitute(self, **kwargs):
        """Safely substitute variables in the translation string."""
        self.substitutions.update(kwargs)
        return self

    def resolve(self, locale: str) -> str:
        lang = translations[locale if locale in translations else "en"]
        translated_message = TemplatedString(lang.gettext(self.key))
        return translated_message.safe_substitute(**self.substitutions)


def resolve_translation(text: str | TranslatedString, locale: str) -> str:
    if isinstance(text, TranslatedString):
        return text.resolve(locale) or ""
    return text or ""


_ = TranslatedString
