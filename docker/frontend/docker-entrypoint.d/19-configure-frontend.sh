#!/bin/sh
set -eu

# Run before nginx's 20-envsubst-on-templates.sh and Certbot's 99 script.
case "${FRONTEND_MODE:-htmx}" in
    react) export FRONTEND_ROOT='try_files $uri $uri/ /index.html;' ;;
    htmx) export FRONTEND_ROOT='error_page 418 = @proxy_api; return 418;' ;;
    *) echo "FRONTEND_MODE must be 'react' or 'htmx'" >&2; exit 1 ;;
esac

# Entrypoint scripts run in separate processes, so render our placeholder here.
# The image's NGINX_ENVSUBST_FILTER limits the standard script to CERTBOT_DOMAIN.
mkdir -p /etc/nginx/templates
envsubst '${FRONTEND_ROOT}' < /etc/nginx/frontend.conf.template \
    > /etc/nginx/templates/default.conf.template
