#!/bin/sh

set -eu

entrypoint_log() {
    if [ -z "${NGINX_ENTRYPOINT_QUIET_LOGS:-}" ]; then
        echo "$@"
    fi
}

# display config
entrypoint_log "$0: Certbot email = ${CERTBOT_EMAIL}";
entrypoint_log "$0: Certbot domain = ${CERTBOT_DOMAIN}";

# request and install cert
if [ -d "/etc/letsencrypt/live" ] && [ "${CERTBOT_DOMAIN}" != "_" ]; then
  if ! grep -q 'managed by Certbot' /etc/nginx/conf.d/default.conf; then
    entrypoint_log "$0: Requesting and installing cert for domain ${CERTBOT_DOMAIN}";
    certbot --email ${CERTBOT_EMAIL} --agree-tos --nginx -d ${CERTBOT_DOMAIN} -n
    nginx -s quit # HACK: certbot seems to start nginx too soon...
  fi
else
  entrypoint_log "$0: Skipped installing cert for domain ${CERTBOT_DOMAIN}";
fi

# check config
entrypoint_log "$0: Checking nginx config";
nginx -t

# add renewal job and start crond
echo '#!/bin/sh' > /etc/periodic/daily/certbot-renew-nginx
echo 'certbot renew --nginx' >> /etc/periodic/daily/certbot-renew-nginx
chmod +x /etc/periodic/daily/certbot-renew-nginx
crond -L /var/log/crond.log -l 5
entrypoint_log "$0: Added daily cert renewal cron job";

# show nginx processes (using cat as it always returns 0)
ps aux | grep nginx | grep process | cat
