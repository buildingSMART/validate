#!/usr/bin/env bash

usage() {
  cat <<EOF
Usage: $(basename "$0") <cert-prefix> <org-country> <org-name>

  <cert-prefix> base name for your cert and key (uses <cert-prefix>.cert.pem and <cert-prefix>.key.pem)
  <org-country> organization country to write into the certificate
  <org-name>    organization name to write into the certificate

Example:
  $(basename "$0") root NL AECgeeks
EOF
  exit 1
}

CONFIG="$(mktemp --suffix=.cnf)"

cat <<EOF > "$CONFIG"
[ v3_ca ]
basicConstraints = critical,CA:TRUE
keyUsage         = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
EOF


if [ "$#" -ne 3 ]; then
  usage
fi

openssl genrsa -out $1.key.pem 4096

openssl req -x509 -new -nodes \
  -key    $1.key.pem \
  -sha256 \
  -days   3650 \
  -out    $1.cert.pem \
  -subj  "/C=$2/O=$3 root" \
  -extensions v3_ca \
  -config    "$CONFIG"

echo "Wrote $1.key.pem and $1.cert.pem"
