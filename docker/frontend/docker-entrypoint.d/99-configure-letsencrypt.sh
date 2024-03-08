#!/bin/sh

set -eu

if [ -d "/etc/letsencrypt/live" ]; then
  if ! grep -q 'managed by Certbot' /etc/nginx/conf.d/default.conf; then
    certbot --email validate@buildingsmart.org --agree-tos --nginx -d dev.validate.buildingsmart.org -n
  fi
fi
