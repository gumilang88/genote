# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""
Deploy the SmartGuestBook contract to GenLayer testnet.

Usage:
    source .venv/bin/activate
    python deploy/deploy.py [--network testnet_bradbury]

Requires .env file with:
    PRIVATE_KEY=your_private_key_here
    RPC_URL=https://rpc-bradbury.genlayer.com
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_env():
    """Load .env file if present."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def deploy_contract():
    parser = argparse.ArgumentParser(description="Deploy SmartGuestBook")
    parser.add_argument(
        "--network",
        default="testnet_bradbury",
        choices=["testnet_bradbury", "testnet_asimov", "studionet", "localnet"],
        help="GenLayer network to deploy to",
    )
    args = parser.parse_args()

    load_env()

    private_key = os.getenv("PRIVATE_KEY")
    rpc_url = os.getenv("RPC_URL", "https://rpc-bradbury.genlayer.com")

    if not private_key:
        print("❌ PRIVATE_KEY not set. Create a .env file with your private key.")
        print("   You can get testnet GEN from: https://testnet-faucet.genlayer.foundation")
        sys.exit(1)

    # Contract source
    contract_path = Path(__file__).parent.parent / "contracts" / "guestbook.py"
    contract_source = contract_path.read_text()

    print(f"🌐 Deploying to {args.network}...")
    print(f"📡 RPC: {rpc_url}")
    print(f"📄 Contract: {contract_path}")

    # Use genlayer-test deploy helper
    from gltest.deploy import deploy_contract as gl_deploy

    address = gl_deploy(
        code=contract_source.encode("utf-8"),
        private_key=private_key,
        rpc_url=rpc_url,
        network=args.network,
    )

    print(f"\n✅ Contract deployed!")
    print(f"   Address: {address}")
    print(f"\n   Next steps:")
    print(f"   1. Update frontend/index.html CONFIG.contractAddress = \"{address}\"")
    print(f"   2. Open frontend/index.html in a browser")
    print(f"   3. Connect MetaMask and submit messages!")

    return address


if __name__ == "__main__":
    deploy_contract()
