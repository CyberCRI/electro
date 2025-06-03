import gettext

from electro.settings import settings
from electro.toolkit.templated_i18n import make_templated_gettext

# Set up `gettext`
en = gettext.translation("messages", localedir=settings.LOCALES_PATH, languages=[settings.BOT_LANGUAGE])
_ = make_templated_gettext(en.gettext)

__all__ = ["_"]
