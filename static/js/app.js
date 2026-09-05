(() => {
  const BASE_CHAIN_ID = window.STOCKTALK?.chainId || 8453;
  const ERC20_ABI = [
    "function allowance(address owner, address spender) view returns (uint256)",
    "function approve(address spender, uint256 value) returns (bool)",
  ];

  const logEl = document.getElementById("log");
  const form = document.getElementById("composer");
  const input = document.getElementById("prompt");
  const sendBtn = document.getElementById("send-btn");
  const walletBtn = document.getElementById("wallet-btn");

  let wallet = null;
  let conversationId = Number(localStorage.getItem("stocktalk.conversationId") || 0) || null;

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

  async function ensureBase() {
    const eth = window.ethereum;
    if (!eth) {
      throw new Error("No browser wallet found. Install MetaMask or a Base-compatible wallet.");
    }
    const chainId = await eth.request({ method: "eth_chainId" });
    if (parseInt(chainId, 16) === BASE_CHAIN_ID) {
      return;
    }
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
    window.ethereum.on?.("chainChanged", () => {
      window.location.reload();
    });
  }

  function renderQuoteCard(action) {
    const card = document.createElement("div");
    card.className = "quote-card";
    const mock = Boolean(action.mock) || action.route === "MOCK";
    const canConfirm = !mock || demoEnabled();

    card.innerHTML = `
      ${mock ? `<div class="mock-tag">MOCK QUOTE</div>` : ""}
      <h3>Confirm swap on Base</h3>
      <div class="quote-row"><span>From</span><strong>${action.from.amount} ${action.from.symbol}</strong></div>
      <div class="quote-row"><span>To</span><strong>${action.to.amount} ${action.to.symbol}</strong></div>
      <div class="quote-row"><span>Impact</span><strong>${action.priceImpactBps ?? 0} bps</strong></div>
      <div class="quote-row"><span>Route</span><strong>${action.route || "0x"}</strong></div>
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
    if (!window.ethereum) {
      throw new Error("Connect a wallet first.");
    }
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;

    await ensureBase();
    if (!wallet) {
      await connectWallet();
    }

    const provider = new ethers.BrowserProvider(window.ethereum);
    const signer = await provider.getSigner();
    const from = await signer.getAddress();
    wallet = from;
    walletBtn.textContent = shortAddr(wallet);
    walletBtn.classList.add("connected");

    const amountWei = BigInt(action.from.amountWei);
    const spender = action.spender;
    if (!spender) {
      throw new Error("Quote is missing a spender.");
    }

    const token = new ethers.Contract(action.from.address, ERC20_ABI, signer);
    const allowance = await token.allowance(from, spender);
    if (allowance < amountWei) {
      append("assistant", "Approve the spender in your wallet, then the swap will follow.");
      const approveTx = await token.approve(spender, amountWei);
      await approveTx.wait();
    }

    const tx = await signer.sendTransaction({
      to: action.tx.to,
      data: action.tx.data,
      value: action.tx.value || 0,
    });
    append("assistant", `Submitted ${tx.hash}`);
    const receipt = await tx.wait();
    const hash = receipt?.hash || tx.hash;

    const res = await fetch("/api/trades", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        quote_id: action.quote_id,
        wallet,
        tx_hash: hash,
      }),
    });
    const body = await res.json();
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
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          wallet,
          conversation_id: conversationId,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        append("assistant", data.error || "Chat failed", "error");
        return;
      }
      conversationId = data.conversation_id;
      localStorage.setItem("stocktalk.conversationId", String(conversationId));
      append("assistant", data.message || "");
      const action = data.action || { type: "none" };
      if (action.type === "quote") {
        renderQuoteCard(action);
      } else if (action.type === "error") {
        append("assistant", action.message || "That ticker is not on the official allowlist.", "error");
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
    if (!text) {
      return;
    }
    input.value = "";
    sendChat(text);
  });

  append(
    "assistant",
    "Hi — I quote official Coinbase Tokenized Stocks on Base. I never sign. Try “swap $2 USD for AAPL”, then confirm in your wallet."
  );
})();
