import binascii
from dataclasses import asdict, dataclass, fields
import datetime
import glob
import json
import os
import subprocess
import sys
import tempfile
from typing import Any, List, Optional
from typing import Tuple
from enum import Enum, auto

# @nb These (rather incomplete) bindings are no
# longer needed, we just use the openssl executable
# from asn1crypto import cms
# from OpenSSL import crypto

# pip install python-ranges
from ranges import Range, RangeSet

import re
import base64

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa, ec
from cryptography.exceptions import InvalidSignature
from cryptography.x509.oid import ExtensionOID


class SignatureVerificationResult(Enum):
    invalid = auto()
    valid_unknown_cert = auto()
    valid_known_cert = auto()


@dataclass
class SignatureData:
    payload: str
    start: int  # start position of the signature block, the beginning of /* within the file
    end: int  # end position of the signature block, the character after */ within the file

    @property
    def signature(self):
        return base64.b64decode(self.payload.encode("ascii"))

    def as_dict(self):
        return {k: format(getattr(self, k)) for k in (f.name for f in fields(self))}

    def verify_pkcs7_openssl(
        self, ca: "CertAuthorityBundle", data: bytes
    ) -> "Tuple[SignatureVerificationResult, Optional[CertificateData]]":
        sig_fd, sig_path = tempfile.mkstemp(suffix=".p7s")
        data_fd, data_path = tempfile.mkstemp(suffix=".dat")
        certout = tempfile.NamedTemporaryFile(delete=False).name
        try:
            with os.fdopen(sig_fd, "wb") as f:
                f.write(self.signature)
            with os.fdopen(data_fd, "wb") as f:
                f.write(data)

            cert_data = None

            # Perform verification up to two times, second time we also verify the chain to
            # see if we have a known vendor root cert. Terminate as soon as verification fails.
            # `-certsout` will write the accepted certificate to disk which we can parse
            for verify_chain in (False, True):
                cmd = [
                    "openssl",
                    "cms",
                    "-verify",
                    "-inform",
                    "DER",
                    "-in",
                    sig_path,
                    "-content",
                    data_path,
                    "-CAfile",
                    ca.filepath,
                    # "-cmsout", "-print",
                    "-certsout",
                    certout,
                    *(("-noverify",) if not verify_chain else ()),
                ]
                result = subprocess.run(cmd, capture_output=True, text=False)
                if result.returncode != 0:
                    return (
                        SignatureVerificationResult.valid_unknown_cert if verify_chain else SignatureVerificationResult.invalid,
                        cert_data,
                    )
                cert_data = CertificateData.from_file(certout, verify=False)
            return SignatureVerificationResult.valid_known_cert, cert_data

        finally:
            # always clean up
            try:
                os.remove(sig_path)
            except OSError:
                pass
            try:
                os.remove(data_path)
            except OSError:
                pass
            try:
                os.remove(certout)
            except OSError:
                pass


@dataclass
class CertificateData:
    certificate: Any
    not_valid_before: datetime
    not_valid_after: datetime
    signature_hash_algorithm_name: str
    rsa_key_size: int
    subject: str
    issuer: str
    fingerprint_hex: str
    serial_number: int

    @staticmethod
    def from_file(fn, verify=True):
        cert = x509.load_pem_x509_certificate(open(fn, "rb").read(), default_backend())

        now = datetime.datetime.now(datetime.timezone.utc)
        if verify and now < cert.not_valid_before_utc:
            raise ValueError("Certificate is not yet valid.")
        elif verify and now > cert.not_valid_after_utc:
            raise ValueError("Certificate has expired.")

        # Check signature hash algorithm
        sig_algo = cert.signature_hash_algorithm
        if verify and sig_algo is None:
            raise ValueError("Signature hash algorithm could not be determined.")
        else:
            algo_name = sig_algo.name.lower()
            if verify and algo_name != "sha256":
                raise ValueError("Signature hash algorithm {algo_name} not supported or deprecated.")

        # Check public key algorithm and parameters
        public_key = cert.public_key()
        key_size = None
        if isinstance(public_key, rsa.RSAPublicKey):
            key_size = public_key.key_size
            if verify and key_size < 2048:
                raise ValueError("RSA key size of {key_size} is less than 2048 bits.")
        elif verify and isinstance(public_key, ec.EllipticCurvePublicKey):
            raise ValueError("Only RSA currently supported")
            # curve_name = public_key.curve.name
            # key_size = public_key.key_size
            # # Recommend using one of the common secure curves.
            # if curve_name not in ['secp256r1', 'secp384r1', 'secp521r1']:
            #     print("Warning: Uncommon elliptic curve used, verify it meets security requirements.")
        elif verify:
            raise ValueError("Unrecognized public key type.")

        if verify and cert.version != x509.Version.v3:
            raise ValueError(f"Certificate version {cert.version.name} is not X.509 v3")

        subject = set(f"{list(v)[0].rfc4514_attribute_name}={list(v)[0].value}" for v in cert.subject.rdns)
        issuer = set(f"{list(v)[0].rfc4514_attribute_name}={list(v)[0].value}" for v in cert.issuer.rdns)
        fingerprint = cert.fingerprint(hashes.SHA256())
        fh = fingerprint.hex().upper()
        fingerprint_hex = ":".join(fh[i : i + 2] for i in range(0, len(fh), 2))

        return CertificateData(
            cert,
            cert.not_valid_before_utc,
            cert.not_valid_after_utc,
            algo_name,
            key_size,
            subject,
            issuer,
            fingerprint_hex,
            cert.serial_number,
        )

    def verify_pkcs7_python(self, signature: SignatureData, content: str) -> bool:
        """
        @nb this is wrong, but leaving it in here in case we do need to do more forensics on the
        CMS structure later on.

        Use: SignatureData.verify_pkcs7_openssl()
        """
        raise NotImplementedError()
        ci = cms.ContentInfo.load(signature.signature)
        if ci["content_type"].native == "signed_data":
            sd = ci["content"]
            eci = sd["encap_content_info"]
            data = eci["content"].native or content[: signature.start].encode("ascii")

            for si in sd["signer_infos"]:
                sid = si["sid"]
                # match by issuer+serial or SKI
                if sid.name == "issuer_and_serial_number":
                    ias = sid.chosen
                    ias_issuer = set(
                        f"{v['type'].human_friendly[0]}={v['value'].native}" for vs in ias["issuer"].chosen for v in vs
                    )

                    if ias_issuer != self.issuer or ias["serial_number"].native != self.serial_number:
                        continue
                else:
                    ski_ext = self.certificate.extensions.get_extension_for_oid(
                        ExtensionOID.SUBJECT_KEY_IDENTIFIER
                    ).value.digest
                    if sid.chosen.native != ski_ext:
                        continue

                sig_bytes = si["signature"].native
                hash_algo = si["digest_algorithm"]["algorithm"].native.upper()
                try:
                    self.certificate.public_key().verify(
                        sig_bytes,
                        data,
                        padding.PKCS1v15(),
                        getattr(hashes, hash_algo)(),
                    )
                    return True
                except InvalidSignature:
                    return False

            return False

    def verify_pkcs1(self, signature, content) -> bool:
        """
        Functional, but currently not in use.

        Use: SignatureData.verify_pkcs7_openssl()
        """

        expected_size = self.certificate.public_key().key_size // 8
        if len(signature.signature) != expected_size:
            return False
            # raise InvalidSignature(
            #     f"Bad signature length: expected {expected_size} bytes, got {len(signature.signature)}"
            # )
        try:
            self.certificate.public_key().verify(
                signature.signature,
                content[: signature.start].encode("ascii"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except binascii.Error as e:
            return False
        except InvalidSignature as e:
            return False

    def as_dict(self):
        excluded_fields = ("certificate",)

        def format(k, v):
            if k in excluded_fields:
                return None
            elif isinstance(v, datetime.datetime):
                return str(v)
            elif isinstance(v, set):
                return ",".join(sorted(v))
            else:
                return v

        return {
            k: format(k, getattr(self, k))
            for k in (f.name for f in fields(self))
            if format(k, getattr(self, k)) is not None
        }


class CertAuthorityBundle:
    def __init__(self, filepath: str):
        self.filepath = filepath

    @staticmethod
    def from_path(dirpath: str):
        ca_bundle_path = tempfile.NamedTemporaryFile(suffix=".pem", delete=False).name
        with open(ca_bundle_path, "wb") as cabundle:
            for pem_path in glob.glob(os.path.join(dirpath, "*.pem")):
                with open(pem_path, "rb") as f:
                    cabundle.write(f.read())
        return CertAuthorityBundle(ca_bundle_path)

    def __del__(self):
        try:
            os.remove(self.filepath)
        except OSError:
            pass


def get_signatures(data: str):
    pattern = r"/\*\s*SIGNATURE;(.+?)ENDSEC;\s*\*/"
    matches = re.finditer(pattern, data, re.DOTALL)
    yield from (SignatureData(m.group(1).strip(), *m.span()) for m in matches)


def strip_content(data: str) -> str:
    return "".join(char for char in data if 0x20 <= ord(char) <= 0xFF and ord(char) != 0x7F)


def run(fn):
    """
    # This was for earlier unsuccessful attempts, still leaving it here in case
    # we need to revisit this or fallback to PKCS#1

    store = crypto.X509Store()
    certificate_store: List[CertificateData] = []

    for fn in glob.glob(os.path.join(os.path.dirname(__file__), "store/*.pem")):
        certificate_store.append(CertificateData.from_file(fn))

    for certdata in certificate_store:
        # `certdata.certificate` is a cryptography.X509Certificate;
        # PyOpenSSL needs an OpenSSL.crypto.X509, so we round-trip via PEM:
        pem = certdata.certificate.public_bytes(Encoding.PEM)
        store.add_cert(crypto.load_certificate(crypto.FILETYPE_PEM, pem))
    """

    ca = CertAuthorityBundle.from_path(os.path.join(os.path.dirname(__file__), "store"))

    with open(fn, "r", encoding="ascii") as f:
        ifc_file = strip_content(f.read())

    sigs = list(get_signatures(ifc_file))

    if not sigs:
        return

    non_signature_ranges = list(Range(0, len(ifc_file)) - RangeSet(Range(sig.start, sig.end) for sig in sigs))

    if len(non_signature_ranges) != 1 or non_signature_ranges[0].start != 0:
        yield {"signature": "invalid"}
        return

    for sig in sigs:
        content_bytes = ifc_file[: sig.start].encode("ascii")
        status, cert = sig.verify_pkcs7_openssl(ca, content_bytes)
        yield {"signature": status.name, **(cert.as_dict() if cert else {}), **sig.as_dict()}


if __name__ == "__main__":
    for res in run(sys.argv[1]):
        print(json.dumps(res))
