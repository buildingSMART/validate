#!/usr/bin/env bash

usage() {
  cat <<EOF
Usage: $(basename "$0") <ca-cert-prefix> <cert-prefix> <org-country> <org-name>

  <ca-cert-prefix> base name for the CA cert to use for signing (uses <ca-cert-prefix>.cert.pem and <ca-cert-prefix>.key.pem)
  <cert-prefix>    base name for your cert and key (uses <cert-prefix>.cert.pem and <cert-prefix>.key.pem)
  <org-country>    organization country to write into the certificate
  <org-name>       organization name to write into the certificate

Example:
  $(basename "$0") leaf root NL AECgeeks
EOF
  exit 1
}

if [ "$#" -ne 4 ]; then
  usage
fi

openssl genrsa -out $2.key.pem 2048

openssl req -new \
  -key $2.key.pem \
  -out $2.csr.pem \
  -subj "/C=$3/O=$4 end-entity"

openssl x509 -req \
  -in $2.csr.pem \
  -CA $1.cert.pem \
  -CAkey $1.key.pem \
  -CAcreateserial \
  -out $2.cert.pem \
  -days 3650

rm -f $2.csr.pem

echo "Wrote $2.key.pem and $2.cert.pem"
