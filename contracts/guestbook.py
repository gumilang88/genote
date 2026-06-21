# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from dataclasses import dataclass
import typing


@allow_storage
@dataclass
class GuestEntry:
    content: str
    timestamp: u256
    image_url: str
    deleted: u256


class SmartGuestBook(gl.Contract):
    entries: DynArray[GuestEntry]
    entry_owners: DynArray[Address]
    aliases: TreeMap[str, str]

    def __init__(self):
        pass

    # ── Display Name ──────────────────────────────────────

    @gl.public.write
    def register_alias(self, name: str):
        name = name.strip()
        if len(name) == 0:
            raise gl.vm.UserError("Name cannot be empty")
        if len(name) > 30:
            raise gl.vm.UserError("Name too long (max 30 chars)")
        self.aliases[str(gl.message.sender_address)] = name

    @gl.public.view
    def get_alias(self, addr: Address) -> str:
        addr_str = str(addr)
        if addr_str in self.aliases:
            return self.aliases[addr_str]
        return ""

    @gl.public.view
    def my_alias(self) -> str:
        addr_str = str(gl.message.sender_address)
        if addr_str in self.aliases:
            return self.aliases[addr_str]
        return ""

    # ── Submit ────────────────────────────────────────────

    @gl.public.write
    def submit(self, content: str):
        if len(content.strip()) == 0:
            raise gl.vm.UserError("Message cannot be empty")
        if len(content) > 2000:
            raise gl.vm.UserError("Message too long (max 2000 chars)")

        ts = u256(len(self.entries) + 1)

        self.entries.append(GuestEntry(
            content=content,
            timestamp=ts,
            image_url="",
            deleted=u256(0),
        ))
        self.entry_owners.append(gl.message.sender_address)

    # ── Delete ────────────────────────────────────────────

    @gl.public.write
    def delete_entry(self, index: u256):
        if index >= len(self.entries):
            raise gl.vm.UserError("Invalid entry index")
        if self.entry_owners[index] != gl.message.sender_address:
            raise gl.vm.UserError("You can only delete your own entries")
        self.entries[index].deleted = u256(1)

    # ── Views ─────────────────────────────────────────────

    @gl.public.view
    def my_count(self) -> int:
        sender = gl.message.sender_address
        count = 0
        for i in range(len(self.entry_owners)):
            if self.entry_owners[i] == sender and self.entries[i].deleted == u256(0):
                count += 1
        return count

    @gl.public.view
    def my_entries(self) -> DynArray[TreeMap[str, typing.Any]]:
        sender = gl.message.sender_address
        result = []
        for i in range(len(self.entry_owners)):
            if self.entry_owners[i] == sender and self.entries[i].deleted == u256(0):
                e = self.entries[i]
                result.append({
                    "index": i,
                    "content": e.content,
                    "timestamp": int(e.timestamp),
                    "image_url": e.image_url,
                })
        return result

    @gl.public.view
    def total_entries(self) -> int:
        count = 0
        for i in range(len(self.entries)):
            if self.entries[i].deleted == u256(0):
                count += 1
        return count

    @gl.public.view
    def total_users(self) -> int:
        seen = set()
        for i in range(len(self.entry_owners)):
            if self.entries[i].deleted == u256(0):
                seen.add(str(self.entry_owners[i]))
        return len(seen)
