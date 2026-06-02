"""
Encryption Service
Handles public-key encryption for client-side settings encryption.
Uses libsodium (NaCl) for asymmetric encryption.

Architecture:
- Backend generates Ed25519 keypair on startup
- Private key stored in environment variable (never in code)
- Public key exposed via /api/public-key endpoint
- Add-ons encrypt settings client-side before sending
- Backend decrypts with private key, applies 2nd-layer Fernet encryption
"""

import os
import sys
import json
import base64
import logging
from typing import Tuple, Optional, Dict, Any

try:
    from nacl.public import PrivateKey, PublicKey
    from nacl.boxes import SealedBox
    from nacl.utils import random
except ImportError as e:
    raise ImportError(
        f"PyNaCl is required but not installed: {e}\n"
        "Please install it with: pip install PyNaCl>=1.5.0"
    )

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Handles libsodium-based encryption for client-server communication.
    
    Public-key encryption workflow:
    1. Backend generates keypair once, stores private key in env var
    2. Backend exposes public key via /api/public-key
    3. Add-on fetches public key, caches locally
    4. Add-on encrypts settings with public key using box_seal()
    5. Add-on sends encrypted payload to /api/settings
    6. Backend decrypts with private key using SealedBox.decrypt()
    """

    def __init__(self):
        """Initialize encryption service by loading private key from environment."""
        self.private_key: Optional[PrivateKey] = None
        self.public_key: Optional[PublicKey] = None
        self._load_keypair()

    def _load_keypair(self) -> None:
        """Load keypair from environment variables. Generate if not present."""
        private_key_b64 = os.environ.get("ENCRYPTION_PRIVATE_KEY", "")
        
        if not private_key_b64:
            # First run - generate keypair
            logger.warning("⚠️  ENCRYPTION_PRIVATE_KEY not set - generating new keypair")
            self._generate_and_save_keypair()
        else:
            # Load existing keypair from env
            try:
                private_key_bytes = base64.b64decode(private_key_b64)
                self.private_key = PrivateKey(private_key_bytes)
                self.public_key = self.private_key.public_key
                logger.info("✅ Encryption keypair loaded from environment")
            except Exception as e:
                logger.error(f"❌ Failed to load encryption keypair: {e}")
                raise ValueError(
                    f"Invalid ENCRYPTION_PRIVATE_KEY format: {e}\n"
                    "Must be a base64-encoded 32-byte private key"
                )

    def _generate_and_save_keypair(self) -> None:
        """Generate new keypair and display for admin to save."""
        logger.info("🔐 Generating new Ed25519 keypair...")
        
        self.private_key = PrivateKey.generate()
        self.public_key = self.private_key.public_key
        
        private_key_b64 = base64.b64encode(bytes(self.private_key)).decode()
        public_key_b64 = base64.b64encode(bytes(self.public_key)).decode()
        
        print("\n" + "="*80, flush=True)
        print("🔐 NEW ENCRYPTION KEYPAIR GENERATED", flush=True)
        print("="*80, flush=True)
        print(f"\n📌 IMPORTANT: Save this to your environment before restarting:\n", flush=True)
        print(f"export ENCRYPTION_PRIVATE_KEY=\"{private_key_b64}\"\n", flush=True)
        print(f"Or in .env file:", flush=True)
        print(f"ENCRYPTION_PRIVATE_KEY={private_key_b64}\n", flush=True)
        print("="*80, flush=True)
        print(f"\n📤 Public Key (share with add-ons / bake into code):\n", flush=True)
        print(f"{public_key_b64}\n", flush=True)
        print("="*80, flush=True)
        sys.stdout.flush()
        
        # Require admin to set env var before continuing
        raise EnvironmentError(
            "ENCRYPTION_PRIVATE_KEY not set. Generated new keypair (see console output above).\n"
            "Set ENCRYPTION_PRIVATE_KEY environment variable and restart the server."
        )

    def get_public_key_b64(self) -> str:
        """
        Get public key as base64 string for distribution to add-ons.
        
        Returns:
            Base64-encoded public key (32 bytes)
        """
        if not self.public_key:
            raise RuntimeError("Encryption service not initialized")
        return base64.b64encode(bytes(self.public_key)).decode()

    def get_public_key_dict(self) -> Dict[str, Any]:
        """
        Get public key metadata for /api/public-key endpoint.
        
        Returns:
            Dict with public_key, algorithm, key_version, etc.
        """
        return {
            "public_key": self.get_public_key_b64(),
            "algorithm": "libsodium/box_seal",
            "key_version": 1,
            "format": "base64"
        }

    def decrypt_settings(self, encrypted_payload_b64: str) -> Dict[str, Any]:
        """
        Decrypt client-encrypted settings using private key.
        
        Args:
            encrypted_payload_b64: Base64-encoded encrypted payload from client
            
        Returns:
            Decrypted settings as dictionary
            
        Raises:
            ValueError: If decryption fails
        """
        if not self.private_key:
            raise RuntimeError("Encryption service not initialized")
        
        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted_payload_b64)
            logger.debug(f"📦 Encrypted payload size: {len(encrypted_bytes)} bytes")
            
            # Decrypt using SealedBox
            box = SealedBox(self.private_key)
            plaintext_bytes = box.decrypt(encrypted_bytes)
            
            # Decode to UTF-8 and parse JSON
            plaintext_str = plaintext_bytes.decode('utf-8')
            settings = json.loads(plaintext_str)
            
            logger.info("✅ Settings decrypted successfully")
            logger.debug(f"📋 Decrypted settings keys: {list(settings.keys())}")
            
            return settings
        
        except Exception as e:
            logger.error(f"❌ Decryption failed: {e}")
            raise ValueError(f"Failed to decrypt settings: {str(e)}")


# Global singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get or create the global encryption service singleton."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def reset_encryption_service() -> None:
    """Reset the encryption service (mainly for testing)."""
    global _encryption_service
    _encryption_service = None
