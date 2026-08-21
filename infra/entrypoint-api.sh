#!/bin/sh
# The API container's entry point.
#
# With a command appended it runs that instead, which is what makes
# `docker compose run --rm api python manage.py migrate` and the retention
# timer work against this same image. Without one it serves.
set -eu

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

# --timeout 30 is the number that matters here. The frontend's api.ts has no
# client-side abort, so a request that hangs forever leaves "Uw advies wordt
# opgehaald" on the screen indefinitely. Thirty seconds is well above the
# measured worst case of about one second and well below a visitor's patience.
#
# Three workers because a computation is CPU bound for about half a second and
# the box is small; more would queue on the same cores and turn one slow
# request into three.
#
# No --access-logfile. gunicorn's access log writes the request line, and the
# request line for a shared advice is /api/advice/<token>/. That is the same
# pairing infra/nginx/nginx.conf goes out of its way not to write, and it would
# land in Docker's json-file driver, which has no rotation and keeps the file
# until the container is removed. Errors still go to stderr, where they belong
# and where they carry no token.
exec gunicorn ampeer.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 30
