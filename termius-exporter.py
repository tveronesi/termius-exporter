#!/usr/bin/env python3
"""
Termius data exporter (Python port)

Extracts and decrypts all data from the local Termius database.
Output: termius_hosts.csv, ssh_keys/, snippets.csv
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def _import_dependencies():
    missing = []
    try:
        import keyring  # type: ignore
        from keyring.errors import KeyringError, NoKeyringError  # type: ignore
    except ImportError:
        keyring = None
        KeyringError = NoKeyringError = Exception
        missing.append("keyring")

    try:
        from nacl.exceptions import CryptoError  # type: ignore
        from nacl.secret import SecretBox  # type: ignore
    except ImportError:
        CryptoError = Exception
        SecretBox = None
        missing.append("PyNaCl")

    if missing:
        pkg_list = " ".join(missing)
        raise SystemExit(
            "Error: Missing required Python dependency"
            + ("ies" if len(missing) > 1 else "")
            + f": {', '.join(missing)}"
            + "\nInstall them with:\n"
            + "  python3 -m pip install -r requirements.txt\n"
            + "or:\n"
            + f"  python3 -m pip install {pkg_list}"
        )

    return keyring, KeyringError, NoKeyringError, CryptoError, SecretBox


keyring, KeyringError, NoKeyringError, CryptoError, SecretBox = _import_dependencies()

BOM = "\ufeff"
OUTPUT_DIR = Path(__file__).resolve().parent
LEVELDB_SUBPATH = ("Termius", "IndexedDB", "file__0.indexeddb.leveldb")
KEY_SERVICES = ("Termius", "com.termius.mac")
KEY_ACCOUNTS = ("localKey", "TermiusKey", "key", "masterKey")
BASE64_BLOCK_RE = re.compile(rb"BA[A-Za-z0-9+/=]{30,}")
BASE64_PASSWORD_RE = re.compile(r"^[A-Za-z0-9+/]{42,}={0,2}$")


def get_db_candidates() -> List[Path]:
    home = Path.home()
    if sys.platform == "darwin":
        sandbox = home / "Library" / "Containers" / "com.termius.mac" / "Data" / "Library" / "Application Support"
        standard = home / "Library" / "Application Support"
        return [
            sandbox.joinpath(*LEVELDB_SUBPATH),
            standard.joinpath(*LEVELDB_SUBPATH),
        ]
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
        return [base.joinpath(*LEVELDB_SUBPATH)]

    base = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
    return [base.joinpath(*LEVELDB_SUBPATH)]


def get_db_path() -> Path:
    candidates = get_db_candidates()
    return next((candidate for candidate in candidates if candidate.exists()), candidates[0])


def parse_manual_key(raw: str) -> bytes:
    value = raw.strip()
    if re.fullmatch(r"[0-9a-fA-F]{64}", value):
        return bytes.fromhex(value)

    clean = re.sub(r"\s+", "", value)
    try:
        decoded = base64.b64decode(clean, validate=False)
    except Exception as exc:
        raise ValueError("Provided key is not valid hex or base64.") from exc

    if len(decoded) == 32:
        return decoded

    raise ValueError(
        f"Provided key does not decode to 32 bytes (got {len(decoded)})."
        " Make sure you copied the full base64 value (~44 chars, usually ending with \"=\")."
    )


def _decode_keychain_value(raw: str) -> Optional[bytes]:
    try:
        decoded = base64.b64decode(raw, validate=False)
    except Exception:
        return None
    return decoded if len(decoded) == 32 else None


def _discover_credentials(service: str) -> List[Tuple[str, Optional[str]]]:
    backend = keyring.get_keyring()
    discovered: List[Tuple[str, Optional[str]]] = []

    finder = getattr(backend, "find_credentials", None)
    if callable(finder):
        try:
            for credential in finder(service, None):
                account = getattr(credential, "username", None)
                password = getattr(credential, "password", None)
                if account:
                    discovered.append((account, password))
        except Exception:
            return []
        return discovered

    getter = getattr(backend, "get_credential", None)
    if callable(getter):
        try:
            credential = getter(service, None)
        except Exception:
            return []
        if credential and getattr(credential, "username", None):
            discovered.append((credential.username, getattr(credential, "password", None)))

    return discovered


def get_encryption_key() -> bytes:
    arg_key = next((arg[len("--key=") :] for arg in sys.argv[1:] if arg.startswith("--key=")), None)
    manual = os.environ.get("TERMIUS_KEY") or arg_key
    if manual:
        print("    ✓ Using manually provided key")
        return parse_manual_key(manual)

    discovered_entries: List[str] = []
    keyring_unavailable = False

    for service in KEY_SERVICES:
        for account in KEY_ACCOUNTS:
            try:
                value = keyring.get_password(service, account)
            except (KeyringError, NoKeyringError):
                keyring_unavailable = True
                value = None
            except Exception:
                value = None
            decoded = _decode_keychain_value(value) if value else None
            if decoded:
                print(f'    ✓ Found keychain entry: service="{service}" account="{account}"')
                return decoded

    for service in KEY_SERVICES:
        for account, password in _discover_credentials(service):
            discovered_entries.append(f"{service} / {account}")
            if password and BASE64_PASSWORD_RE.fullmatch(password):
                decoded = _decode_keychain_value(password)
                if decoded:
                    print(f'    ✓ Auto-discovered key: service="{service}" account="{account}"')
                    return decoded

    if discovered_entries:
        found = "\nKeychain entries found:\n  - " + "\n  - ".join(discovered_entries)
    elif keyring_unavailable:
        found = "\nCould not read keychain (sandboxed Termius keys are ACL-protected)."
    else:
        found = "\nCould not read keychain (sandboxed Termius keys are ACL-protected)."

    script_name = Path(__file__).name
    raise RuntimeError(
        "Termius encryption key not found."
        + found
        + "\n\nManual key fallback:"
        + '\n  1) Open Keychain Access, search "Termius"'
        + '\n  2) Double-click the entry → check "Show password", copy the value (~44 char base64)'
        + f"\n  3) Re-run:  TERMIUS_KEY='<value>' python3 {script_name}"
        + f"\n     or:     python3 {script_name} --key='<value>'"
    )


def decrypt(base64_data: bytes, key: bytes) -> Optional[str]:
    try:
        data = base64.b64decode(base64_data, validate=False)
    except Exception:
        return None

    if not data or data[0] != 4 or len(data) < 26:
        return None

    nonce = data[2:26]
    ciphertext = data[26:]

    try:
        decrypted = SecretBox(key).decrypt(ciphertext, nonce)
    except CryptoError:
        return None

    try:
        return decrypted.decode("utf-8")
    except UnicodeDecodeError:
        return None


def extract_and_decrypt(key: bytes) -> List[str]:
    db_path = get_db_path()
    if not db_path.exists():
        raise RuntimeError(f"Termius database not found at: {db_path}")

    files = [entry for entry in sorted(db_path.iterdir()) if entry.suffix in {".log", ".ldb"}]

    all_data = bytearray()
    for file_path in files:
        all_data.extend(file_path.read_bytes())

    encrypted: List[bytes] = []
    seen = set()
    for match in BASE64_BLOCK_RE.findall(bytes(all_data)):
        if match not in seen:
            seen.add(match)
            encrypted.append(match)

    print(f"Found {len(encrypted)} encrypted blocks")

    results: List[str] = []
    for item in encrypted:
        decrypted = decrypt(item, key)
        if decrypted is not None:
            results.append(decrypted)

    pct = f"{(len(results) / len(encrypted) * 100):.1f}" if encrypted else "0.0"
    print(f"Decrypted: {len(results)}/{len(encrypted)} ({pct}%)")
    return results


def parse_decrypted_data(results: Iterable[str]) -> Dict[str, object]:
    identities_by_user: Dict[str, dict] = {}
    keys_by_label: Dict[str, dict] = {}
    keys_by_id: Dict[str, dict] = {}
    connections: List[dict] = []
    snippets: Dict[str, dict] = {}

    for item in results:
        if not item.startswith("{"):
            continue
        try:
            obj = json.loads(item)
        except json.JSONDecodeError:
            continue

        if obj.get("username") is not None and obj.get("password") is not None:
            map_key = obj.get("label") or obj.get("username")
            if map_key not in identities_by_user or obj.get("password"):
                identities_by_user[map_key] = obj

        if obj.get("private_key") and obj.get("label"):
            keys_by_label[obj["label"]] = obj
            if obj.get("id"):
                keys_by_id[obj["id"]] = obj

        if obj.get("host") and obj.get("user_name") and obj.get("connection_type"):
            connections.append(obj)

        if obj.get("script") and obj.get("label"):
            snippets[obj["label"]] = obj

    return {
        "identitiesByUser": identities_by_user,
        "keysByLabel": keys_by_label,
        "keysById": keys_by_id,
        "connections": connections,
        "snippets": snippets,
    }


def escape_csv(value: object) -> str:
    text = "" if value is None else str(value)
    if re.match(r"^[=+\-@\t\r]", text):
        text = "'" + text
    return '"' + text.replace('"', '""') + '"'


def build_host_config(data: Dict[str, object]) -> Dict[str, dict]:
    identities_by_user: Dict[str, dict] = data["identitiesByUser"]  # type: ignore[assignment]
    keys_by_id: Dict[str, dict] = data["keysById"]  # type: ignore[assignment]
    connections: List[dict] = data["connections"]  # type: ignore[assignment]

    host_map: Dict[str, dict] = {}
    for conn in connections:
        port_key = "undefined" if conn.get("port") is None else str(conn.get("port"))
        key = f'{conn.get("host")}:{port_key}'
        if key in host_map:
            continue

        password = ""
        for identity in identities_by_user.values():
            if identity.get("username") == conn.get("user_name") and identity.get("password"):
                password = identity["password"]

        key_name = ""
        if conn.get("key_id"):
            key_obj = keys_by_id.get(conn["key_id"])
            key_name = key_obj["label"] if key_obj else f'key_id:{conn["key_id"]}'

        host_map[key] = {
            "host": conn.get("host"),
            "port": conn.get("port"),
            "label": conn.get("title") or "",
            "username": conn.get("user_name"),
            "password": password,
            "keyName": key_name,
            "os": conn.get("host_os_name") or "",
        }

    return host_map


def _write_text(path: Path, content: str, mode: int, newline: str = "") -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8", newline=newline) as handle:
        handle.write(content)


def export_hosts_csv(host_map: Dict[str, dict]) -> int:
    lines = ["Label,Host,Port,Username,Password,SSH_Key,OS\n"]
    for host in host_map.values():
        lines.append(
            ",".join(
                escape_csv(value)
                for value in (
                    host["label"],
                    host["host"],
                    host["port"],
                    host["username"],
                    host["password"],
                    host["keyName"],
                    host["os"],
                )
            )
            + "\n"
        )

    _write_text(OUTPUT_DIR / "termius_hosts.csv", BOM + "".join(lines), 0o600)
    return len(host_map)


def export_ssh_keys(keys_by_label: Dict[str, dict]) -> int:
    keys_dir = OUTPUT_DIR / "ssh_keys"
    if not keys_dir.exists():
        keys_dir.mkdir(mode=0o700)

    count = 0
    for label, key_obj in keys_by_label.items():
        private_key = key_obj.get("private_key")
        if not private_key:
            continue

        safe_name = re.sub(r'[<>:"/\\|?*]', "_", label)
        key_content = private_key if private_key.endswith("\n") else private_key + "\n"

        _write_text(keys_dir / f"{safe_name}.pem", key_content, 0o600)

        if key_obj.get("passphrase"):
            _write_text(keys_dir / f"{safe_name}.passphrase", key_obj["passphrase"], 0o600)

        count += 1

    return count


def export_snippets(snippets: Dict[str, dict]) -> int:
    lines = ["Label,Script\n"]
    for label, snippet in snippets.items():
        script = (snippet.get("script") or "").replace('"', '""').replace("\n", "\\n")
        lines.append(f'"{label}","{script}"\n')

    _write_text(OUTPUT_DIR / "snippets.csv", BOM + "".join(lines), 0o600)
    return len(snippets)


def main() -> None:
    print("=== Termius Data Exporter ===\n")

    print("[1/4] Retrieving encryption key...")
    key = get_encryption_key()
    print("    ✓ Key retrieved\n")

    print("[2/4] Decrypting database...")
    results = extract_and_decrypt(key)
    print("")

    print("[3/4] Parsing data...")
    data = parse_decrypted_data(results)
    print(f'    ✓ Identities: {len(data["identitiesByUser"])}')
    print(f'    ✓ SSH keys:   {len(data["keysByLabel"])}')
    print(f'    ✓ Connections:{len(data["connections"])}')
    print(f'    ✓ Snippets:   {len(data["snippets"])}\n')

    print("[4/4] Exporting...")
    host_map = build_host_config(data)
    hosts_count = export_hosts_csv(host_map)
    keys_count = export_ssh_keys(data["keysByLabel"])  # type: ignore[arg-type]
    snippets_count = export_snippets(data["snippets"])  # type: ignore[arg-type]

    print(f"    ✓ termius_hosts.csv ({hosts_count} hosts)")
    print(f"    ✓ ssh_keys/ ({keys_count} keys)")
    print(f"    ✓ snippets.csv ({snippets_count} snippets)\n")

    print("=== Export complete ===")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1)
