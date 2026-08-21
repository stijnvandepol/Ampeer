"""The production entry point, and the only settings module it may serve.

The assignment below is not a setdefault. Django's generated wsgi.py uses one,
and with it an exported DJANGO_SETTINGS_MODULE wins: a stray
`DJANGO_SETTINGS_MODULE=ampeer.settings.dev` in a unit file or a compose file
would serve public traffic with DEBUG on, ALLOWED_HOSTS on localhost and a
SECRET_KEY that is written out in this repository, and nothing anywhere would
report it. This file exists only to serve production, so it names production
and refuses to be talked out of it.

tests/test_backend_settings.py asserts the module named here, and the quality
job runs `manage.py check --deploy --fail-level WARNING` against that same
module so a settings mistake fails a pull request rather than a deploy.
"""

from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application

os.environ["DJANGO_SETTINGS_MODULE"] = "ampeer.settings.prod"
application = get_wsgi_application()
