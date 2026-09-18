import os
import gettext

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALE_DIR = os.path.join(BASE_DIR, 'locales')
DOMAIN = 'messages'

_current_translation = gettext.NullTranslations()  # no-op fallback until set_language() is called


def set_language(lang_code: str) -> None:
    """Switch the active language at runtime."""
    global _current_translation
    _current_translation = gettext.translation(
        DOMAIN,
        localedir=LOCALE_DIR,
        languages=[lang_code],
        fallback=True,
    )


def _(message: str) -> str:
    """Translate a string using the currently active language."""
    return _current_translation.gettext(message)

set_language('en')  # default language