"""Offline, repository-name-based Ed25519 software licensing.

Author: Mishal Mohanlal  |  Version: 0.1.0

Only the admin's *encrypted private key* can issue licences. Client programs
ship only a public key. The app ID is the repository name, never owner/repo.
"""
from __future__ import annotations

import base64
import calendar
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

VERSION = "0.1.0"
AUTHOR = "Mishal Mohanlal"
COMPANY = "The Project Company"
_FORMAT = 1
_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_MACHINE = re.compile(r"^[A-F0-9]{8}(?:-[A-F0-9]{8}){3}$")


class LicenceError(ValueError):
    """A licence, identity or signing operation could not be validated."""


def repository_name(name: str) -> str:
    """Canonical application ID: GitHub repository name WITHOUT owner/account."""
    value = name.strip().lower()
    if not _REPOSITORY.fullmatch(value) or value in {".", ".."}:
        raise LicenceError("Enter the repository name only (e.g. smlz_to_robot), not owner/repo.")
    return value


def _good_hardware_value(value: str) -> bool:
    token = value.strip().upper().replace("-", "").replace(" ", "")
    if len(token) < 8 or token in {"0" * len(token), "F" * len(token)}:
        return False
    return not any(s in value.lower() for s in ("to be filled", "default string", "not specified", "unknown"))


def _device_identifier() -> tuple[str, str]:
    """Prefer hardware UUID; gracefully fall back to persistent OS installation ID."""
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"],
                capture_output=True, text=True, timeout=8, check=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for line in result.stdout.splitlines():
                value = line.strip()
                if _good_hardware_value(value):
                    return "smbios-uuid", value.upper()
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                value, _ = winreg.QueryValueEx(key, "MachineGuid")
            if _good_hardware_value(str(value)):
                return "windows-machineguid", str(value).upper()
        except (OSError, ImportError):
            pass
    else:
        for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                value = Path(path).read_text(encoding="utf-8").strip()
                if _good_hardware_value(value):
                    return "os-machine-id", value.upper()
            except OSError:
                pass
    # Last resort. MAC identifiers can change and may be shared in virtual machines.
    mac = uuid.getnode()
    if mac and mac != 0xFFFFFFFFFFFF:
        return "mac-fallback", f"{mac:012X}"
    raise LicenceError("Unable to establish a stable machine ID on this computer.")


def machine_id() -> str:
    """Stable hashed 128-bit identifier, displayed as XXXX... groups of 8."""
    kind, value = _device_identifier()
    digest = hashlib.sha256(f"TPC-LICENCE-V1|{kind}|{value}".encode("utf-8")).hexdigest()[:32].upper()
    return "-".join(digest[i:i + 8] for i in range(0, 32, 8))


def normalize_machine_id(value: str) -> str:
    token = value.strip().upper().replace(" ", "")
    if not _MACHINE.fullmatch(token):
        raise LicenceError("Machine ID must contain four groups of eight hexadecimal digits.")
    return token


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("naive timestamp")
        return parsed.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError) as exc:
        raise LicenceError("Invalid licence timestamp.") from exc


def add_months(moment: datetime, months: int) -> datetime:
    """Calendar anniversary: Jan 31 + 1 month = Feb 28/29."""
    if not 1 <= months <= 120:
        raise LicenceError("Licence duration must be between 1 and 120 months.")
    n = moment.year * 12 + moment.month - 1 + months
    year, zero_month = divmod(n, 12)
    month = zero_month + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def _canonical_json(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def generate_signing_key(path: str | Path, password: str) -> Path:
    """Generate an encrypted private key; NEVER copy it into a client project."""
    destination = Path(path).expanduser()
    if len(password) < 12:
        raise LicenceError("Use a private-key password of at least 12 characters.")
    if destination.exists():
        raise LicenceError("Signing key already exists. It will not be overwritten.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(password.encode("utf-8")),
    )
    # x mode guarantees an existing key is not silently overwritten.
    with destination.open("xb") as handle:
        handle.write(pem)
    if os.name != "nt":
        destination.chmod(0o600)
    return destination


def _load_private_key(path: str | Path, password: str) -> Ed25519PrivateKey:
    try:
        key = serialization.load_pem_private_key(Path(path).read_bytes(), password=password.encode("utf-8"))
        if not isinstance(key, Ed25519PrivateKey):
            raise LicenceError("Signing key is not an Ed25519 private key.")
        return key
    except (OSError, ValueError, TypeError) as exc:
        raise LicenceError("Cannot open signing key. Check the key file and password.") from exc


def export_public_key(private_key_path: str | Path, password: str, destination: str | Path) -> Path:
    key = _load_private_key(private_key_path, password)
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    target = Path(destination).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(pem)
    return target


def _public_key(data: bytes | str | Path) -> Ed25519PublicKey:
    if isinstance(data, Path):
        content = data.read_bytes()
    elif isinstance(data, bytes):
        content = data
    elif isinstance(data, str):
        content = data.encode("utf-8") if "-----BEGIN" in data else Path(data).read_bytes()
    else:
        raise LicenceError("Invalid public key argument.")
    try:
        key = serialization.load_pem_public_key(content)
    except (ValueError, TypeError) as exc:
        raise LicenceError("Invalid PEM public key.") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise LicenceError("Expected Ed25519 public key.")
    return key


def _key_id(key: Ed25519PublicKey) -> str:
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:16]


def issue_licence(
    private_key_path: str | Path, password: str, application: str,
    hardware_id: str, *, customer: str = "", months: int = 12,
    now: datetime | None = None,
) -> dict:
    """Issue cryptographically signed offline licence for one repo + computer."""
    key = _load_private_key(private_key_path, password)
    issued = now or _utc_now()
    if issued.tzinfo is None:
        raise LicenceError("Issue time must include a timezone.")
    payload = {
        "schema": _FORMAT,
        "licence_id": str(uuid.uuid4()),
        "application": repository_name(application),
        "machine_id": normalize_machine_id(hardware_id),
        "customer": customer.strip()[:200],
        "issuer": COMPANY,
        "issued_at": _timestamp(issued),
        "expires_at": _timestamp(add_months(issued, months)),
    }
    signature = key.sign(_canonical_json(payload))
    return {
        "payload": payload,
        "key_id": _key_id(key.public_key()),
        "signature": base64.b64encode(signature).decode("ascii"),
    }


def save_licence(licence: dict, destination: str | Path) -> Path:
    target = Path(destination).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(licence, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return target


def verify_licence(
    licence: dict | str | Path, public_key: bytes | str | Path,
    application: str, hardware_id: str | None = None,
    *, now: datetime | None = None,
) -> dict:
    """Return verified claims, or raise LicenceError (including for expiry)."""
    try:
        if isinstance(licence, (str, Path)):
            document = json.loads(Path(licence).read_text(encoding="utf-8"))
        else:
            document = licence
        if not isinstance(document, dict) or set(document) != {"payload", "key_id", "signature"}:
            raise LicenceError("Malformed licence envelope.")
        payload = document["payload"]
        if not isinstance(payload, dict):
            raise LicenceError("Malformed licence claims.")
        expected = {"schema", "licence_id", "application", "machine_id", "customer", "issuer", "issued_at", "expires_at"}
        if set(payload) != expected or type(payload["schema"]) is not int or payload["schema"] != _FORMAT:
            raise LicenceError("Unsupported licence format.")
        if not all(isinstance(payload[field], str) for field in expected - {"schema"}):
            raise LicenceError("Invalid licence fields.")
        key = _public_key(public_key)
        if document["key_id"] != _key_id(key):
            raise LicenceError("Licence was signed by a different issuer key.")
        signature = base64.b64decode(document["signature"], validate=True)
        key.verify(signature, _canonical_json(payload))
        if payload["application"] != repository_name(application):
            raise LicenceError(f"Licence is for '{payload['application']}', not '{repository_name(application)}'.")
        current_id = normalize_machine_id(hardware_id if hardware_id is not None else machine_id())
        if payload["machine_id"] != current_id:
            raise LicenceError("Licence belongs to another computer.")
        issued, expires = _read_timestamp(payload["issued_at"]), _read_timestamp(payload["expires_at"])
        current = now or _utc_now()
        if current.tzinfo is None:
            raise LicenceError("Current time must include a timezone.")
        if expires <= issued or current < issued or current >= expires:
            raise LicenceError("Licence is not yet active or has expired.")
        return payload.copy()
    except InvalidSignature as exc:
        raise LicenceError("Signature invalid: licence contents were changed or forged.") from exc
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, base64.binascii.Error) as exc:
        if isinstance(exc, LicenceError):
            raise
        raise LicenceError(f"Cannot validate licence: {exc}") from exc


def licence_location(application: str) -> Path:
    root = os.environ.get("LOCALAPPDATA") if os.name == "nt" else os.environ.get("XDG_DATA_HOME")
    base = Path(root) if root else Path.home() / ".local" / "share"
    return base / "TPC" / "Licences" / f"{repository_name(application)}.lic"


def install_licence(source: str | Path, public_key: bytes | str | Path, application: str) -> Path:
    """Validate first; then install to a deterministic user-writable location."""
    verify_licence(source, public_key, application)
    target = licence_location(application)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target) if Path(source).resolve() != target.resolve() else None
    return target


def require_licence(application: str, public_key: bytes | str | Path) -> dict:
    """Headless integration point. Raises LicenceError when not activated."""
    path = licence_location(application)
    if not path.exists():
        raise LicenceError("No licence installed. Activate this application first.")
    return verify_licence(path, public_key, application)
