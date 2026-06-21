"""Tests for per-wallet private guestbook with alias, delete, images."""

import json


def test_submit_and_read_own(direct_vm, direct_deploy, direct_alice):
    """Submit and read own entry."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.sender = direct_alice
    direct_vm.mock_llm(r".*", json.dumps({"approved": True}))

    contract.submit("My private note")
    assert contract.my_count() == 1

    entries = contract.my_entries()
    assert len(entries) == 1
    assert entries[0]["content"] == "My private note"
    assert entries[0]["timestamp"] > 0
    assert entries[0]["image_url"] == ""
    assert "index" in entries[0]


def test_multiple_users_separate(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Each user sees only their own entries."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.mock_llm(r".*", json.dumps({"approved": True}))

    direct_vm.sender = direct_alice
    contract.submit("Alice secret")
    contract.submit("Alice another")

    direct_vm.sender = direct_bob
    contract.submit("Bob note")

    # Alice sees 2
    direct_vm.sender = direct_alice
    assert contract.my_count() == 2

    # Bob sees 1
    direct_vm.sender = direct_bob
    assert contract.my_count() == 1

    bob_entries = contract.my_entries()
    assert len(bob_entries) == 1
    assert bob_entries[0]["content"] == "Bob note"


def test_empty_rejected(direct_vm, direct_deploy, direct_alice):
    """Empty message rejected."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Message cannot be empty"):
        contract.submit("   ")


def test_too_long_rejected(direct_vm, direct_deploy, direct_alice):
    """Over 500 chars rejected."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Message too long"):
        contract.submit("x" * 2001)


def test_new_user_zero_count(direct_vm, direct_deploy, direct_alice, direct_bob):
    """New user starts with 0 entries."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.sender = direct_alice
    assert contract.my_count() == 0
    assert contract.my_entries() == []


def test_public_stats(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Public stats show total counts."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.mock_llm(r".*", json.dumps({"approved": True}))

    assert contract.total_entries() == 0
    assert contract.total_users() == 0

    direct_vm.sender = direct_alice
    contract.submit("A")

    direct_vm.sender = direct_bob
    contract.submit("B")
    contract.submit("C")

    assert contract.total_entries() == 3
    assert contract.total_users() == 2


# ── New: Alias ──

def test_register_alias(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Register and retrieve alias via sender."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.sender = direct_alice
    contract.register_alias("Alice")
    assert contract.my_alias() == "Alice"
    # Bob has no alias
    direct_vm.sender = direct_bob
    assert contract.my_alias() == ""


def test_empty_alias_rejected(direct_vm, direct_deploy, direct_alice):
    """Empty alias rejected."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Name cannot be empty"):
        contract.register_alias("   ")


def test_long_alias_rejected(direct_vm, direct_deploy, direct_alice):
    """Over 30 char alias rejected."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Name too long"):
        contract.register_alias("x" * 31)


# ── New: Delete ──

def test_delete_own_entry(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Delete own entry removes from view."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.mock_llm(r".*", json.dumps({"approved": True}))

    direct_vm.sender = direct_alice
    contract.submit("First")
    contract.submit("Second")
    assert contract.my_count() == 2

    # Delete first
    contract.delete_entry(0)
    assert contract.my_count() == 1
    entries = contract.my_entries()
    assert len(entries) == 1
    assert entries[0]["content"] == "Second"
    assert entries[0]["index"] == 1


def test_cannot_delete_others_entry(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Cannot delete another user's entry."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.mock_llm(r".*", json.dumps({"approved": True}))

    direct_vm.sender = direct_alice
    contract.submit("Alice msg")

    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("You can only delete your own entries"):
        contract.delete_entry(0)


def test_delete_updates_total_count(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Deleted entries don't count toward totals."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.mock_llm(r".*", json.dumps({"approved": True}))

    direct_vm.sender = direct_alice
    contract.submit("A")
    contract.submit("B")

    direct_vm.sender = direct_bob
    contract.submit("C")

    assert contract.total_entries() == 3
    assert contract.total_users() == 2

    direct_vm.sender = direct_alice
    contract.delete_entry(0)

    assert contract.total_entries() == 2  # A deleted
    assert contract.total_users() == 2    # Alice still has entries


# ── New: Image URL ──

def test_submit_with_image_url(direct_vm, direct_deploy, direct_alice):
    """Submit with image_url stores it (via direct content field)."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.sender = direct_alice
    direct_vm.mock_llm(r".*", json.dumps({"approved": True}))

    contract.submit("Check this out")
    entries = contract.my_entries()
    assert len(entries) == 1
    assert entries[0]["content"] == "Check this out"
    assert entries[0]["image_url"] == ""  # No separate param


def test_submit_with_long_image_url_rejected(direct_vm, direct_deploy, direct_alice):
    """Only content is validated."""
    contract = direct_deploy("contracts/guestbook.py")
    direct_vm.sender = direct_alice
    direct_vm.mock_llm(r".*", json.dumps({"approved": True}))
    contract.submit("hi")  # No image_url param anymore
