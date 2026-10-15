"""Verify ALB-signed user claims against configured deployment identity.

These are ALB user-info tokens, not Cognito ID/access tokens. Unsigned identity
headers and browser user IDs are never used as authentication evidence.
"""
import asyncio
import base64
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import inspect
import json
import re
import time
from urllib.parse import urlsplit


class AuthenticationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthenticatedIdentity:
    principal: str
    expires_at: int


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuthenticationError("Duplicate identity claim")
        result[key] = value
    return result


class AlbIdentityVerifier:
    def __init__(self, *, signer_arn, issuer, client_id, key_fetcher=None, clock=time.time):
        match = re.fullmatch(r"arn:aws:elasticloadbalancing:([a-z]{2}(?:-[a-z]+)+-\d+):\d{12}:loadbalancer/app/[A-Za-z0-9-]{1,32}/[a-f0-9]{16}", signer_arn or "")
        parsed = urlsplit(issuer or "")
        if (match is None or match[1].startswith("us-gov-") or parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or any(c.isspace() for c in issuer)):
            raise ValueError("Configure the exact commercial AWS ALB ARN and HTTPS issuer")
        if not isinstance(client_id, str) or not 1 <= len(client_id) <= 512 or any(c.isspace() for c in client_id):
            raise ValueError("Configure the exact identity-provider client ID")
        if key_fetcher is not None and not inspect.iscoroutinefunction(key_fetcher):
            raise ValueError("Key fetcher must be async")
        self.signer_arn, self.issuer, self.client_id = signer_arn, issuer, client_id
        self.region, self._clock, self._fetcher = match[1], clock, key_fetcher or self._fetch
        self._keys, self._key_lock = OrderedDict(), asyncio.Lock()

    async def _fetch(self, url):
        import aiohttp
        async with aiohttp.ClientSession(trust_env=False, timeout=aiohttp.ClientTimeout(total=5),
                                         cookie_jar=aiohttp.DummyCookieJar()) as client:
            async with client.get(url, allow_redirects=False) as response:
                if response.status != 200:
                    raise AuthenticationError("Identity signing key unavailable")
                body = bytearray()
                async for chunk in response.content.iter_chunked(1024):
                    body.extend(chunk)
                    if len(body) > 4096:
                        raise AuthenticationError("Identity signing key exceeds limit")
                return bytes(body)

    async def _key(self, kid):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        # Serializing cache misses bounds concurrent key fetches and avoids
        # duplicate downloads for concurrent requests using the same key.
        async with self._key_lock:
            now = self._clock()
            if kid in self._keys and self._keys[kid][0] > now:
                self._keys.move_to_end(kid)
                return self._keys[kid][1]
            raw = await self._fetcher(f"https://public-keys.auth.elb.{self.region}.amazonaws.com/{kid}")
            if not isinstance(raw, bytes) or not 1 <= len(raw) <= 4096:
                raise AuthenticationError("Invalid identity signing key")
            key = serialization.load_pem_public_key(raw)
            if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
                raise AuthenticationError("Expected an ES256 signing key")
            self._keys[kid] = (self._clock() + 900, key)
            self._keys.move_to_end(kid)
            while len(self._keys) > 16:
                self._keys.popitem(last=False)
            return key

    async def verify(self, token):
        try:
            if not isinstance(token, str) or not 1 <= len(token) <= 16384:
                raise AuthenticationError("Invalid identity token")
            segments = token.split(".")
            if len(segments) != 3 or any(not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", part) for part in segments):
                raise AuthenticationError("Invalid identity token encoding")
            # Strict parsing is additional input validation. PyJWT verifies the
            # signature over the original compact token, not reconstructed JSON.
            decoded = [json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)), object_pairs_hook=_object)
                       for part in segments[:2]]
            header, payload = decoded
            if not isinstance(header, dict) or not isinstance(payload, dict):
                raise AuthenticationError("Invalid identity token shape")
            if (set(header) - {"alg", "kid", "signer", "iss", "client", "exp", "typ"}
                    or header.get("alg") != "ES256" or header.get("signer") != self.signer_arn
                    or header.get("iss") != self.issuer or header.get("client") != self.client_id
                    or header.get("typ", "JWT") != "JWT"):
                raise AuthenticationError("Unexpected identity token authority")
            kid = header.get("kid")
            if not isinstance(kid, str) or not re.fullmatch(r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}", kid):
                raise AuthenticationError("Invalid identity signing key ID")
            expiry = header.get("exp")
            if type(expiry) is str and re.fullmatch(r"[0-9]{1,12}", expiry):
                expiry = int(expiry)
            if type(expiry) is not int or not self._clock() < expiry <= self._clock() + 604800:
                raise AuthenticationError("Identity token is expired or has an invalid lifetime")
            import jwt
            async with asyncio.timeout(6):
                key = await self._key(kid)
            verified = jwt.decode_complete(token, key, algorithms=["ES256"], options={"verify_aud": False, "verify_iss": False})
            if verified["header"] != header or verified["payload"] != payload or expiry <= self._clock():
                raise AuthenticationError("Identity token changed or expired during verification")
            subject = payload.get("sub")
            if not isinstance(subject, str) or not 1 <= len(subject) <= 512 or any(ord(c) < 32 for c in subject):
                raise AuthenticationError("A verified subject is required")
            principal = "id_" + hashlib.sha256(json.dumps([self.issuer, subject], separators=(",", ":")).encode()).hexdigest()
            return AuthenticatedIdentity(principal, expiry)
        except asyncio.CancelledError:
            raise
        except Exception:
            raise AuthenticationError("Authentication failed") from None
