#!/usr/bin/env python3

import argparse
import base64
import json
import re
import unicodedata

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


BASE58BTC_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58BTC_INDEX = {
    character: index
    for index, character in enumerate(BASE58BTC_ALPHABET)
}

INVISIBLE_CATEGORIES = frozenset({
    "Cc",
    "Cf",
    "Cs",
    "Co",
    "Zl",
    "Zp",
})

DID_PATTERN = re.compile(r"^did:key:z6Mk[1-9A-HJ-NP-Za-km-z]{44}$")


def base58btc_decode(value):
    number = 0

    for character in value:
        if character not in BASE58BTC_INDEX:
            raise ValueError(f"invalid base58 character: {character!r}")
        number = number * 58 + BASE58BTC_INDEX[character]

    decoded = (
        number.to_bytes((number.bit_length() + 7) // 8, "big")
        if number
        else b""
    )

    zeroes = len(value) - len(value.lstrip("1"))
    return b"\x00" * zeroes + decoded


def normalize_message(text):
    return "".join(
        " "
        if unicodedata.category(character) in INVISIBLE_CATEGORIES
        else character
        for character in text
    ).strip()


def public_key_from_did(did):
    if not DID_PATTERN.fullmatch(did):
        raise ValueError(
            "DID must be a canonical Ed25519 did:key:z6Mk... identifier"
        )

    multibase = did[len("did:key:"):]
    decoded = base58btc_decode(multibase[1:])

    if len(decoded) != 34:
        raise ValueError("DID does not contain a valid Ed25519 public key")

    if decoded[:2] != b"\xed\x01":
        raise ValueError("DID does not contain the Ed25519 multicodec")

    return Ed25519PublicKey.from_public_bytes(decoded[2:])


def build_payload(room, nonce, text):
    normalized = normalize_message(text)
    return f"{room}|{nonce}|{normalized}".encode("utf-8")


def verify_message(room, nonce, text, did, signature):
    payload = build_payload(room, nonce, text)
    public_key = public_key_from_did(did)

    raw_signature = base64.urlsafe_b64decode(signature + "==")
    public_key.verify(raw_signature, payload)

    return payload


def inspect_message(message):
    room = message["room"]
    nonce = message["nonce"]
    text = message["text"]
    did = message["from"]
    signature = message.get("signature")

    normalized = normalize_message(text)
    payload = build_payload(room, nonce, text)

    print()
    print("Technocore Message Inspector")
    print("=" * 32)
    print(f"Room:       {room}")
    print(f"Sequence:   {message.get('seq', 'unknown')}")
    print(f"Timestamp:  {message.get('ts', 'unknown')}")
    print(f"DID:        {did}")
    print(f"Nonce:      {nonce}")
    print()
    print("Original text:")
    print(text)
    print()
    print("Normalized text:")
    print(normalized)
    print()
    print("Signed payload:")
    print(payload.decode("utf-8"))

    if signature:
        try:
            verify_message(room, nonce, text, did, signature)
            print()
            print("Signature:  VALID")
        except (ValueError, InvalidSignature) as error:
            print()
            print(f"Signature:  INVALID ({error})")
    else:
        print()
        print("Signature:  not supplied")


def main():
    parser = argparse.ArgumentParser(
        description="Inspect and verify Technocore signed messages."
    )

    parser.add_argument(
        "message",
        help="JSON file containing one Technocore message",
    )

    args = parser.parse_args()

    with open(args.message, "r", encoding="utf-8") as file:
        message = json.load(file)

    inspect_message(message)


if __name__ == "__main__":
    main()
