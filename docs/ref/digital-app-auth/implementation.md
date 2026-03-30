## Implementation Guidelines for Developers

### Overview of the Signature Process

The digital authentication process for IFC files involves generating a hash of the file's content, encrypting this hash
with a vendor's private key, and appending the resulting signature along with the public certificate to the IFC file.
The Validation Service, or any consuming application, can then decrypt the signature using the vendor's public key,
re-hash the file content, and compare the two hashes to verify integrity and authenticity.

![Figure – Signature Process Overview](./signature-process-overview.jpg)
```{image} ../../_static/digital_app_auth_process_overview.png
:alt: Digital Application Authentication process overview
:scale: 100 %
:align: center
```
*Figure 1 – Signature Process Overview*

The table below explains the terms used in the figure above.

| Term                                   | Meaning                                                                                                                                                                                                      | Location                                        |
|----------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------|
| Certificate Authority (CA) Private Key | The private key of the Certificate Authority (CA). It is used to **sign other CA certificates** (e.g., vendor or leaf certs). Highly secure, never exposed.                                                  | Private and stays with the issuing vendor       |
| CA Certificate                         | The **public certificate** of the CA. It includes the CA's public key and is used to **verify signatures** created with the CA key. This certificate is **trusted by default.**                              | Published on the buildingSMART GitHub repo      |
| Leaf Private Key                       | The private key of the actual **end-entity** (e.g., a specific software tool or product). It signs the actual IFC file.                                                                                      | In the signature comment block of the IFC file  |
| Leaf CSR (Certificate Signing Request) | A request generated using the leaf key, containing the public key and identity info. It's sent to a CA to obtain a signed certificate (Leaf certificate).                                                    | —                                               |
| Leaf Certificate                       | A certificate issued to the leaf entity (the signer of the IFC file), signed by a CA (or intermediate CA). It includes the public key that the IFC Validation Service uses to verify the IFC file signature. | Bundled in the IFC signature block (CMS format) |

### Signature Block Structure

- **Placement in IFC File**: The digital signature block is appended to the end of the IFC file, specifically after the
  `END-ISO-10303;` line.

- **Syntax**: To remain compliant with the IFC standard (ISO 16739-1), which specify the ISO 10303-21:**2002** (Step
  Physical File Format) as primary exchange format, the signature is wrapped within a comment block. The general
  structure is as follows:

```
1. ENDSEC;
2. /*
3. SIGNATURE;
4. <Actual Digital Signature Data>
5. ENDSEC;
6. */
```

In the future, if IFC will change its reference to newer versions of the STEP standard (
e.g.  [ISO 10303-21:2016](https://www.iso.org/standard/63141.html), where anchors, references and signature sections are
supported), a proper signature section can be considered. For now, the comment mimics the exact format of the STEP
signature section.

### File Content for Hashing

- **Ignoring Line Endings**: When computing the hash for the digital signature, carriage return (`0x0D`) and new line (
  `0x0A`) characters are ignored — as well as all characters that are not valid according to the 10303-21 syntax. This
  addresses potential issues arising from different operating systems (e.g., Windows vs. Linux) handling line endings
  differently, which would otherwise invalidate signatures upon re-saving.

- **Strict Interpretation of File Content**: The hash should be calculated on the file content up to the start of the
  commented signature block. A strict interpretation suggests treating the file content as a binary BLOB (Binary Large
  Object) for hashing. This means that any semantic or non-semantic changes (e.g., changes in instance order, white
  space, or character encoding shifts) will likely invalidate the signature unless explicitly ignored. The current
  consensus leans towards being strict: if a user opens an IFC file in a text editor and re-saves it, potentially
  altering the content, the breaking of the signature is considered an acceptable indication of tampering.

### Key and Certificate Management

- **Generating Private Keys**: Software vendors are responsible for generating and securely storing their private keys.
  The process can be straightforward; for example, generating a key using SSH-keygen or similar tools can take mere
  minutes for a skilled engineer.

- **Submitting Public Certificates to buildingSMART**: Once a private key is generated, the corresponding public
  certificate (which includes metadata like the vendor's name) should be submitted to buildingSMART. This is done by
  opening a pull request to the designated GitHub
  folder ([buildingsmart-certificates/validation-service-vendor-certificates](https://github.com/buildingsmart-certificates/validation-service-vendor-certificates)).

- **Chain of Trust (Optional Advanced Usage)**: While a simple direct trust model (vendor provides public key,
  buildingSMART trusts it) is initially sufficient, the framework supports longer chains of trust. This means a root
  certificate (e.g., from a vendor like Autodesk) could sign subsidiary certificates (e.g., for specific products like
  Revit). The Validation Service can then verify these chains, and allows the root keys to remain private, especially as
  the signing of subsidiary keys happens on vendor infrastructure.

### Cryptographic Standards and Tools

- **Hashing Algorithms**: The underlying hash function and encryption method for digital signatures can be implemented
  using widely available open-source tools. The OpenSSL library is a common choice for proof-of-concept prototypes due
  to its native C++ support.

- **Signature Encoding**: Discussions have revolved around using PKCS #1 versus PKCS #7 for signature encoding. After
  careful consideration, PKCS #7 (corresponding to CMS — Cryptographic Message Syntax) has been adopted — mainly because
  it is more suitable for API exchange, it is the one suggested in the STEP 10303-21 standard, and it supports
  additional metadata and can bundle other public certificates.

- **Utilising Existing Libraries**: The [step-authorize](https://github.com/steptools/STEPAuthorize) GitHub repository
  offers code that can be modified to generate comments before and after the signature. It also provides compiled
  binaries and supports different modes for signature and certificate output (e.g., separate blobs or a combined CMS
  BLOB). This can be a useful starting point for developers.

### Important Considerations and Best Practices

- **Cumulative Signatures**: Digital signatures, as implemented, are cumulative. This implies that removing an earlier
  signature in a sequence will invalidate all subsequent signatures.

- **Handling Leaked Private Keys**: In the event of a private key leak, the ability to "unauthorise" or revoke the key
  is crucial. buildingSMART aims to establish procedures for this, akin to a Certificate Authority.

- **Serialization Agnosticism**: As noted, minor changes to an IFC file (like white space or instance order) will break
  a signature. The decision to ignore carriage returns and new lines helps, but strict adherence to file content for
  hashing is generally preferred to maintain integrity.

- **IFC SPF vs. IFC XML**: This digital signature feature is currently designed for IFC SPF (Standard Physical File)
  format, not IFC XML, as XML is not within the current scope of the Validation Service.

- **Adding Comments to Signatures**: Currently, the agreed signature structure doesn't allow for any data besides the
  command open/close, signature begin/end markers and the payload. Implementers can always add data as a separate
  comment that *precedes* the signature comment — if needed — or embed data in the CMS message structure.

### Additional resources

A 30 minutes video containing a detailed demo of the feature can be
found [here](https://app.box.com/s/x2nft1hfyzp7kzhj3xulrp2drhtubl5g).

For support, email <validate@buildingsmart.org>
