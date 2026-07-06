# secrets/

Docker Compose mounts `ed25519_private_key.b64` from this directory into the backend container
at `/run/secrets/ed25519_private_key` (Compose's file-based secrets mechanism) — this is the
"mounted file" the private signing key is loaded from. **The real key file is gitignored and must
never be committed.**

Generate one:

```bash
python -c "
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

priv = Ed25519PrivateKey.generate()
priv_bytes = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
pub_bytes = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

print('Private key (save to secrets/ed25519_private_key.b64):', base64.b64encode(priv_bytes).decode())
print('Public key (give to whoever configures the agent):', base64.b64encode(pub_bytes).decode())
"
```

Save the private key line's value (just the base64 string, nothing else) to
`secrets/ed25519_private_key.b64`. Distribute the public key value to whoever configures the
ElevateGate agent's `ElevateGate:ServerPublicKeyBase64` setting — see docs/API_CONTRACT.md.
