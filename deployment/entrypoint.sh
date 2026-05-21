#!/bin/sh

set -e

export PROJECT_NAME=djass

export DJANGO_SETTINGS_MODULE="djass.settings"

process_type="${DJASS_PROCESS_TYPE:-server}"

while getopts ":sw" option; do
    case "${option}" in
        s)  # Run server
            process_type="server"
            ;;
        w)  # Run worker
            process_type="worker"
            ;;
        *)  # Invalid option
            echo "Invalid option: -$OPTARG" >&2
            exit 1
            ;;
    esac
done
shift $((OPTIND - 1))

case "$process_type" in
    server)
        python manage.py collectstatic --noinput
        python manage.py migrate
        gunicorn ${PROJECT_NAME}.wsgi:application --bind 0.0.0.0:80 --workers 3 --threads 2
        ;;
    worker|workers)
        python manage.py qcluster
        ;;
    *)
        echo "Invalid DJASS_PROCESS_TYPE: $process_type. Expected 'server' or 'worker'." >&2
        exit 1
        ;;
esac
