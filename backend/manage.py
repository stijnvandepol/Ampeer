# No shebang. Ruff's EXE001 refuses a shebang on a file without the
# executable bit, and that bit cannot be represented on the Windows
# checkout this repository is developed on, so the two would drift and
# only CI would ever see it. Nothing here runs ./manage.py; every call
# site uses `python backend/manage.py`.
from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ampeer.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
