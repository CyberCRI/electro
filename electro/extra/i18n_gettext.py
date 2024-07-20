import gettext

from ..settings import settings
from ..toolkit.templated_i18n import make_templated_gettext

# Set up `gettext`
en = gettext.translation("messages", localedir=settings.LOCALES_PATH, languages=[settings.BOT_LANGUAGE])
templated_gettext = make_templated_gettext(en.gettext)

__all__ = ["templated_gettext"]
