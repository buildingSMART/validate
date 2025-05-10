#!/usr/bin/env bash

usage() {
  cat <<EOF
Usage: $(basename "$0") <cert-prefix> <input> <output>

  <cert-prefix> base name for your cert and key (uses <cert-prefix>.cert.pem and <cert-prefix>.key.pem)
  <input>       path to the IFC file you want to sign
  <output>      path to the signed output

Example:
  $(basename "$0") mycert input.ifc signed_output.ifc
EOF
  exit 1
}

if [ "$#" -ne 3 ]; then
  usage
fi

DATAFILE="$2"
OUTFILE="$3"
CERT="$1.cert.pem"
KEY="$1.key.pem"
TMPSIG="$(mktemp --suffix=.b64)"
TMPDATA="$(mktemp)"

# Initialize the output with the original data
cp "$DATAFILE" "$OUTFILE"

# Add opening marker
printf "\n/*SIGNATURE;\n" >> "$OUTFILE"

# Create a filtered version of the data (strip chars <0x20 and 0x7F)
#    – \000–\037 are ASCII 0–31
#    – \177 is DEL (127)
tr -d '\000-\037\177' < "$DATAFILE" > "$TMPDATA"

# Generate a detached (by default) CMS signature in ASN1 DER form and convert to base64
openssl cms -sign \
  -in  "$TMPDATA" \
  -signer "$CERT" \
  -inkey  "$KEY" \
  -outform DER | openssl base64 > "$TMPSIG"

# Append the signature
cat "$TMPSIG" >> "$OUTFILE"

# Append closing marker
printf "ENDSEC;*/\n" >> "$OUTFILE"

# Clean up
rm -f "$TMPSIG" "$TMPDATA"

echo "Wrote signed file: $OUTFILE"
