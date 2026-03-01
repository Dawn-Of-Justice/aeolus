"""
aeolus/network/messages.py
Message serialisation / deserialisation helpers.
"""
from __future__ import annotations

from aeolus.negotiation.capability import AgentCapabilityDocument, NegotiationMessage


def encode_message(msg: NegotiationMessage) -> bytes:
    return msg.model_dump_json().encode("utf-8")


def decode_message(data: bytes) -> NegotiationMessage:
    return NegotiationMessage.model_validate_json(data)


def encode_acd(acd: AgentCapabilityDocument) -> bytes:
    return acd.model_dump_json().encode("utf-8")


def decode_acd(data: bytes) -> AgentCapabilityDocument:
    return AgentCapabilityDocument.model_validate_json(data)
