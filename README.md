# Smart GuestBook — AI-Moderated Guestbook on GenLayer

A decentralized guestbook where messages are **moderated by AI** before being stored on the GenLayer testnet. Uses Intelligent Contracts with LLM-powered content moderation.

## Quick Start

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

## Project Structure

```
smart-guestbook/
├── contracts/
│   └── guestbook.py       # Intelligent Contract (Python)
├── tests/
│   └── test_guestbook.py   # Direct mode tests
├── frontend/
│   └── index.html          # Web app (standalone HTML)
├── deploy/
│   └── deploy.py           # Deploy script
├── gltest.config.yaml      # Network configuration
└── requirements.txt
```

## How It Works

1. User submits a message via the web app (MetaMask wallet)
2. Transaction hits the GenLayer testnet
3. Contract calls LLM (`gl.nondet.exec_prompt`) to check if the message is appropriate
4. If approved → message is stored on-chain
5. If rejected → transaction reverts with error

## Deploy to Testnet (Bradbury)

### 1. Get testnet GEN
Go to [GenLayer Faucet](https://testnet-faucet.genlayer.foundation) and request testnet GEN.

### 2. Create .env file
```bash
echo "PRIVATE_KEY=your_private_key_here" > .env
echo "RPC_URL=https://rpc-bradbury.genlayer.com" >> .env
```
> ⚠️ Never commit your .env file! It's in .gitignore.

### 3. Deploy
```bash
source .venv/bin/activate
python deploy/deploy.py --network testnet_bradbury
```

### 4. Update Frontend
Set the contract address in `frontend/index.html`:
```javascript
const CONFIG = {
  rpcUrl: "https://rpc-bradbury.genlayer.com",
  contractAddress: "0xYOUR_DEPLOYED_CONTRACT_ADDRESS",
  // ...
};
```

### 5. Open Frontend
Open `frontend/index.html` in a browser. Connect MetaMask and start writing messages!

## Testing

Direct mode tests run in-memory — no server or Docker needed:

```bash
pytest tests/ -v
```

Tests verify:
- ✅ Clean messages are approved and stored
- ✅ Spam/inappropriate messages are rejected
- ✅ Empty/overly-long messages are rejected
- ✅ Multiple users can post
- ✅ Out-of-bounds access is handled

## Networks

| Network | RPC URL | Chain ID | 
|---------|---------|----------|
| Bradbury Testnet | https://rpc-bradbury.genlayer.com | 4221 |
| Asimov Testnet | https://rpc-asimov.genlayer.com | 4221 |
| Studio | https://studio.genlayer.com/api | 61999 |
| Localnet | http://localhost:4000/api | 61127 |

## Contract API

### Write Methods
- `submit(content: str)` — Submit a message (AI-moderated)

### View Methods
- `get_count() -> int` — Total approved messages
- `get_entry(index: int) -> dict` — Get message by index
- `get_all() -> list[dict]` — Get all messages
