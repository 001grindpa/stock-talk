(() => {
  const BASE_CHAIN_ID = window.STOCKTALK?.chainId || 8453;
  const ERC20_ABI = [
    "function balanceOf(address owner) view returns (uint256)",
    "function decimals() view returns (uint8)",
    "function allowance(address owner, address spender) view returns (uint256)",
    "function approve(address spender, uint256 value) returns (bool)",
  ];

  const logEl = document.getElementById("log");
  const form = document.getElementById("composer");
  const input = document.getElementById("prompt");
  const sendBtn = document.getElementById("send-btn");
  const walletBtn = document.getElementById("wallet-btn");

  let wallet = null;
  let tokens = [];
  let extraTokens = [];
  let conversationId = null;
  const threadId =
    (window.crypto && crypto.randomUUID && crypto.randomUUID()) ||
    `session-${Date.now()}`;

  function sessionThread() {
    return threadId;
  }

  function demoEnabled() {
    const params = new URLSearchParams(window.location.search);
    return (
      window.STOCKTALK?.demoAllowMock === true ||
      params.get("demo") === "1" ||
      localStorage.getItem("stocktalkDemo") === "1"
    );
  }

  function append(role, text, extraClass) {
    const el = document.createElement("div");
    el.className = `msg ${role}${extraClass ? ` ${extraClass}` : ""}`;
    el.textContent = text;
    logEl.appendChild(el);
    logEl.scrollTop = logEl.scrollHeight;
    return el;
  }

  function appendHtml(node) {
    logEl.appendChild(node);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function shortAddr(addr) {
    return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
  }

  function hexChain(id) {
    return `0x${Number(id).toString(16)}`;
  }

  function rememberToken(token) {
    if (!token?.address) return;
    const addr = token.address.toLowerCase();
    const exists = [...tokens, ...extraTokens].some(
      (item) => item.address.toLowerCase() === addr
    );
    if (!exists) {
      extraTokens.push({
        symbol: token.symbol || "TOKEN",
        address: token.address,
        decimals: token.decimals ?? 18,
      });
    }
  }

  async function loadTokens() {
    const res = await fetch("/api/tokens");
    const data = await res.json();
    tokens = data.tokens || [];
  }

  async function readBalances() {
    if (!wallet || !window.ethereum) return [];
    const provider = new ethers.BrowserProvider(window.ethereum);
    const list = [...tokens, ...extraTokens];
    const out = [];
    for (const token of list) {
      try {
        const contract = new ethers.Contract(token.address, ERC20_ABI, provider);
        const raw = await contract.balanceOf(wallet);
        out.push({
          symbol: token.symbol,
          address: token.address,
          decimals: token.decimals,
          raw: raw.toString(),
          formatted: ethers.formatUnits(raw, token.decimals),
        });
      } catch (_err) {}
    }
    return out;
  }

  async function ensureBase() {
    const eth = window.ethereum;
    if (!eth) {
      throw new Error("No browser wallet found. Install MetaMask or a Base-compatible wallet.");
    }
    const chainId = await eth.request({ method: "eth_chainId" });
    if (parseInt(chainId, 16) === BASE_CHAIN_ID) return;
    try {
      await eth.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: hexChain(BASE_CHAIN_ID) }],
      });
    } catch (err) {
      if (err?.code === 4902) {
        await eth.request({
          method: "wallet_addEthereumChain",
          params: [
            {
              chainId: hexChain(BASE_CHAIN_ID),
              chainName: "Base",
              nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
              rpcUrls: ["https://mainnet.base.org"],
              blockExplorerUrls: ["https://basescan.org"],
            },
          ],
        });
        return;
      }
      throw err;
    }
  }

  async function connectWallet() {
    if (!window.ethereum) {
      append("assistant", "No injected wallet. Install MetaMask and refresh.", "error");
      return;
    }
    await ensureBase();
    const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
    wallet = accounts[0];
    walletBtn.textContent = shortAddr(wallet);
    walletBtn.classList.add("connected");
    if (!tokens.length) await loadTokens();
  }

  walletBtn.addEventListener("click", () => {
    connectWallet().catch((err) => append("assistant", err.message || String(err), "error"));
  });

  if (window.ethereum) {
    window.ethereum.on?.("accountsChanged", (accounts) => {
      wallet = accounts?.[0] || null;
      walletBtn.textContent = wallet ? shortAddr(wallet) : "Connect wallet";
      walletBtn.classList.toggle("connected", Boolean(wallet));
    });
    window.ethereum.on?.("chainChanged", () => window.location.reload());
  }

  function renderQuoteCard(action) {
    const card = document.createElement("div");
    card.className = "quote-card";
    const mock = Boolean(action.mock) || action.route === "MOCK";
    const canConfirm = !mock || demoEnabled();
    const isLp = action.type === "tx";
    const title = isLp
      ? action.summary || "Confirm Aerodrome LP on Base"
      : "Confirm swap on Base";
    const fromLabel = action.from
      ? `${action.from.amount} ${action.from.symbol}`
      : "—";
    const toLabel = action.to
      ? `${action.to.amount} ${action.to.symbol}`
      : "—";
    const routeLabel = action.protocol || action.route || action.kind || "aerodrome";

    card.innerHTML = `
      ${mock ? `<div class="mock-tag">MOCK</div>` : ""}
      <h3>${title}</h3>
      <div class="quote-row"><span>From</span><strong>${fromLabel}</strong></div>
      <div class="quote-row"><span>To</span><strong>${toLabel}</strong></div>
      <div class="quote-row"><span>Route</span><strong>${routeLabel}</strong></div>
      <div class="confirm-actions">
        <button type="button" class="confirm" ${canConfirm ? "" : "disabled"}>Confirm in wallet</button>
        <button type="button" class="cancel">Cancel</button>
      </div>
    `;

    const confirmBtn = card.querySelector(".confirm");
    const cancelBtn = card.querySelector(".cancel");
    cancelBtn.addEventListener("click", () => {
      confirmBtn.disabled = true;
      cancelBtn.disabled = true;
      append("assistant", "Cancelled. No wallet prompt was sent.");
    });
    confirmBtn.addEventListener("click", () => {
      executeQuote(action, confirmBtn, cancelBtn).catch((err) => {
        append("assistant", err?.shortMessage || err?.message || String(err), "error");
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
      });
    });
    appendHtml(card);
  }

  async function executeQuote(action, confirmBtn, cancelBtn) {
    if (!window.ethereum) throw new Error("Connect a wallet first.");
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;

    await ensureBase();
    if (!wallet) await connectWallet();

    const provider = new ethers.BrowserProvider(window.ethereum);
    const signer = await provider.getSigner();
    const from = await signer.getAddress();
    wallet = from;
    walletBtn.textContent = shortAddr(wallet);
    walletBtn.classList.add("connected");

    const spender = action.spender;
    if (!spender) throw new Error("Quote is missing a spender.");
    if (!action.tx?.to || !action.tx?.data) throw new Error("Quote is missing transaction data.");

    const approvals = action.approvals?.length
      ? action.approvals
      : [
          {
            address: action.from.address,
            amountWei: action.from.amountWei,
            symbol: action.from.symbol,
          },
        ];

    for (const item of approvals) {
      rememberToken(item);
      const token = new ethers.Contract(item.address, ERC20_ABI, signer);
      const amountWei = BigInt(item.amountWei);
      const allowance = await token.allowance(from, spender);
      if (allowance < amountWei) {
        append("assistant", `Approve ${item.symbol || "token"} in your wallet.`);
        const approveTx = await token.approve(spender, amountWei);
        await approveTx.wait();
      }
    }

    const tx = await signer.sendTransaction({
      to: action.tx.to,
      data: action.tx.data,
      value: action.tx.value || 0,
    });
    append("assistant", `Submitted ${tx.hash}`);
    const receipt = await tx.wait();
    const hash = receipt?.hash || tx.hash;

    if (action.raw?.pool) {
      rememberToken({
        symbol: "AERO-LP",
        address: action.raw.pool,
        decimals: 18,
      });
    }

    const res = await fetch("/api/trades", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quote_id: action.quote_id, wallet, tx_hash: hash }),
    });
    const body = await res.json().catch(() => ({}));
    const url = body.explorer || `https://basescan.org/tx/${hash}`;
    const link = document.createElement("div");
    link.className = "msg assistant";
    link.innerHTML = `Trade recorded. <a href="${url}" target="_blank" rel="noopener">View on Basescan</a>`;
    appendHtml(link);
  }

  async function sendChat(text) {
    append("user", text);
    sendBtn.disabled = true;
    try {
      if (!tokens.length) await loadTokens();
      const balances = wallet ? await readBalances() : [];
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          wallet,
          conversation_id: conversationId,
          thread_id: sessionThread(),
          balances,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        append("assistant", data.error || "Chat failed", "error");
        return;
      }
      conversationId = data.conversation_id;
      if (data.message) append("assistant", data.message);
      if (data.action?.type === "quote" || data.action?.type === "tx") {
        if (data.action.raw?.pool) {
          rememberToken({
            symbol: "AERO-LP",
            address: data.action.raw.pool,
            decimals: 18,
          });
        }
        renderQuoteCard(data.action);
      }
    } catch (err) {
      append("assistant", err.message || String(err), "error");
    } finally {
      sendBtn.disabled = false;
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    sendChat(text);
  });

  loadTokens().catch(() => {});
})();