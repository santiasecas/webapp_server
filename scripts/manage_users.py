#!/usr/bin/env python3
"""
scripts/manage_users.py — Manage platform users and groups.

Commands:
  add    <username> [password]  --groups admins,users  [--display-name "Full Name"]
  delete <username>
  passwd <username> [password]
  list   [--group <group>]
  groups
  verify <username> [password]
  group-add    <username> <group>
  group-remove <username> <group>

Options:
  --file PATH   Path to .users.json (default: .users.json)

Examples:
  python scripts/manage_users.py add admin --groups admins,users
  python scripts/manage_users.py add alice --groups users --display-name "Alice Smith"
  python scripts/manage_users.py list
  python scripts/manage_users.py list --group admins
  python scripts/manage_users.py group-add alice editors
  python scripts/manage_users.py groups
"""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_FILE = ".users.json"

# ── File I/O ──────────────────────────────────────────────────────────────────

def load_file(filepath: str) -> dict:
    path = Path(filepath)
    if not path.exists():
        return {"users": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "users" not in data:
        data["users"] = {}
    return data


def save_file(filepath: str, data: dict) -> None:
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep non-user keys (like _comment) when saving
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {path}")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(args):
    from core.auth_passwords import hash_password_bcrypt

    data = load_file(args.file)
    users = data["users"]

    if args.username in users and not getattr(args, "force", False):
        print(f"  Error: user '{args.username}' already exists. Use --force to overwrite.")
        sys.exit(1)

    password = getattr(args, "password", None) or getpass.getpass(f"  Password for '{args.username}': ")
    if not password:
        print("  Error: password cannot be empty.")
        sys.exit(1)

    groups_raw = getattr(args, "groups", "users") or "users"
    groups = [g.strip() for g in groups_raw.split(",") if g.strip()]
    if not groups:
        groups = ["users"]

    display_name = getattr(args, "display_name", "") or args.username

    users[args.username] = {
        "password_hash": hash_password_bcrypt(password),
        "groups": groups,
        "display_name": display_name,
        "active": True,
    }
    save_file(args.file, data)
    print(f"  ✓ User '{args.username}' saved  |  groups: {groups}  |  display: {display_name!r}")


def cmd_delete(args):
    data = load_file(args.file)
    if args.username not in data["users"]:
        print(f"  Error: user '{args.username}' not found.")
        sys.exit(1)
    del data["users"][args.username]
    save_file(args.file, data)
    print(f"  ✓ Deleted user '{args.username}'")


def cmd_passwd(args):
    from core.auth_passwords import hash_password_bcrypt

    data = load_file(args.file)
    if args.username not in data["users"]:
        print(f"  Error: user '{args.username}' not found.")
        sys.exit(1)

    password = getattr(args, "password", None) or getpass.getpass(f"  New password for '{args.username}': ")
    if not password:
        print("  Error: password cannot be empty.")
        sys.exit(1)

    data["users"][args.username]["password_hash"] = hash_password_bcrypt(password)
    save_file(args.file, data)
    print(f"  ✓ Password updated for '{args.username}'")


def cmd_list(args):
    data = load_file(args.file)
    users = data["users"]

    group_filter = getattr(args, "group", None)
    if group_filter:
        users = {k: v for k, v in users.items() if group_filter in v.get("groups", [])}

    if not users:
        filter_info = f" in group '{group_filter}'" if group_filter else ""
        print(f"  No users found{filter_info} in {args.file}")
        return

    header = f"{'Username':<24} {'Display Name':<24} {'Groups':<30} {'Active'}"
    print(f"\n  {header}")
    print(f"  {'-' * len(header)}")
    for username, info in sorted(users.items()):
        groups = ", ".join(info.get("groups", []))
        display = info.get("display_name", username)
        active = "✓" if info.get("active", True) else "✗ disabled"
        print(f"  {username:<24} {display:<24} {groups:<30} {active}")
    print()


def cmd_groups(args):
    data = load_file(args.file)
    group_members: dict[str, list[str]] = {}

    for username, info in data["users"].items():
        for g in info.get("groups", []):
            group_members.setdefault(g, []).append(username)

    if not group_members:
        print(f"  No groups found in {args.file}")
        return

    print(f"\n  Groups in {args.file}:\n")
    for group in sorted(group_members):
        members = ", ".join(sorted(group_members[group]))
        print(f"  {group:<24} ({len(group_members[group])} member{'s' if len(group_members[group]) != 1 else ''}): {members}")
    print()


def cmd_verify(args):
    from core.auth_passwords import verify_password

    data = load_file(args.file)
    if args.username not in data["users"]:
        print(f"  Error: user '{args.username}' not found.")
        sys.exit(1)

    password = getattr(args, "password", None) or getpass.getpass(f"  Password for '{args.username}': ")
    info = data["users"][args.username]

    if not info.get("active", True):
        print(f"  ✗ User '{args.username}' is disabled.")
        sys.exit(1)

    if verify_password(password, info["password_hash"]):
        print(f"  ✓ Password correct for '{args.username}'  |  groups: {info.get('groups', [])}")
    else:
        print(f"  ✗ Invalid password for '{args.username}'")
        sys.exit(1)


def cmd_group_add(args):
    data = load_file(args.file)
    if args.username not in data["users"]:
        print(f"  Error: user '{args.username}' not found.")
        sys.exit(1)
    groups = data["users"][args.username].setdefault("groups", [])
    if args.group in groups:
        print(f"  User '{args.username}' is already in group '{args.group}'")
        return
    groups.append(args.group)
    save_file(args.file, data)
    print(f"  ✓ Added '{args.username}' to group '{args.group}'  |  groups now: {groups}")


def cmd_group_remove(args):
    data = load_file(args.file)
    if args.username not in data["users"]:
        print(f"  Error: user '{args.username}' not found.")
        sys.exit(1)
    groups = data["users"][args.username].get("groups", [])
    if args.group not in groups:
        print(f"  User '{args.username}' is not in group '{args.group}'")
        return
    groups.remove(args.group)
    if not groups:
        print(f"  Warning: '{args.username}' now has no groups. Adding 'users' as fallback.")
        groups.append("users")
    data["users"][args.username]["groups"] = groups
    save_file(args.file, data)
    print(f"  ✓ Removed '{args.username}' from group '{args.group}'  |  groups now: {groups}")


def cmd_disable(args):
    data = load_file(args.file)
    if args.username not in data["users"]:
        print(f"  Error: user '{args.username}' not found.")
        sys.exit(1)
    data["users"][args.username]["active"] = False
    save_file(args.file, data)
    print(f"  ✓ Disabled user '{args.username}' (login blocked, record preserved)")


def cmd_enable(args):
    data = load_file(args.file)
    if args.username not in data["users"]:
        print(f"  Error: user '{args.username}' not found.")
        sys.exit(1)
    data["users"][args.username]["active"] = True
    save_file(args.file, data)
    print(f"  ✓ Enabled user '{args.username}'")


# ── CLI parser ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Manage Corporate Platform users and groups",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--file", default=DEFAULT_FILE, help="Path to .users.json")
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p = sub.add_parser("add", help="Add or update a user")
    p.add_argument("username")
    p.add_argument("password", nargs="?", default=None)
    p.add_argument("--groups", default="users",
                   help="Comma-separated list of groups (default: users)")
    p.add_argument("--display-name", dest="display_name", default="",
                   help="Human-readable name")
    p.add_argument("--force", action="store_true", help="Overwrite if exists")

    # delete
    p = sub.add_parser("delete", help="Delete a user permanently")
    p.add_argument("username")

    # passwd
    p = sub.add_parser("passwd", help="Change a user's password")
    p.add_argument("username")
    p.add_argument("password", nargs="?", default=None)

    # list
    p = sub.add_parser("list", help="List users")
    p.add_argument("--group", default=None, help="Filter by group")

    # groups
    sub.add_parser("groups", help="List all groups and their members")

    # verify
    p = sub.add_parser("verify", help="Verify a user's password")
    p.add_argument("username")
    p.add_argument("password", nargs="?", default=None)

    # group-add
    p = sub.add_parser("group-add", help="Add a user to a group")
    p.add_argument("username")
    p.add_argument("group")

    # group-remove
    p = sub.add_parser("group-remove", help="Remove a user from a group")
    p.add_argument("username")
    p.add_argument("group")

    # disable / enable
    p = sub.add_parser("disable", help="Disable a user (block login without deleting)")
    p.add_argument("username")
    p = sub.add_parser("enable", help="Re-enable a disabled user")
    p.add_argument("username")

    args = parser.parse_args()
    dispatch = {
        "add":          cmd_add,
        "delete":       cmd_delete,
        "passwd":       cmd_passwd,
        "list":         cmd_list,
        "groups":       cmd_groups,
        "verify":       cmd_verify,
        "group-add":    cmd_group_add,
        "group-remove": cmd_group_remove,
        "disable":      cmd_disable,
        "enable":       cmd_enable,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
