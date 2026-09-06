document.addEventListener("DOMContentLoaded", () => {
  const pageId = document.body.id;

  initTheme();

  const yearEl = document.getElementById("footer-year");
  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }

  if (pageId === "landing") {
    initLanding();
  } else if (pageId === "index") {
    initIndex();
  }
});

function initTheme() {
  const THEME_KEY = "stocktalk.theme";
  const themeBtn = document.getElementById("theme-toggle-btn");

  function applyTheme(theme) {
    if (theme === "light") {
      document.body.classList.add("light-theme");
      if (themeBtn) {
        const sunIcon = themeBtn.querySelector(".theme-icon-sun");
        const moonIcon = themeBtn.querySelector(".theme-icon-moon");
        if (sunIcon) sunIcon.style.display = "none";
        if (moonIcon) moonIcon.style.display = "block";
      }
    } else {
      document.body.classList.remove("light-theme");
      if (themeBtn) {
        const sunIcon = themeBtn.querySelector(".theme-icon-sun");
        const moonIcon = themeBtn.querySelector(".theme-icon-moon");
        if (sunIcon) sunIcon.style.display = "block";
        if (moonIcon) moonIcon.style.display = "none";
      }
    }
  }

  const savedTheme = localStorage.getItem(THEME_KEY) || "dark";
  applyTheme(savedTheme);

  themeBtn?.addEventListener("click", () => {
    const isLight = document.body.classList.contains("light-theme");
    const nextTheme = isLight ? "dark" : "light";
    localStorage.setItem(THEME_KEY, nextTheme);
    applyTheme(nextTheme);
  });
}

function initLanding() {
  const ENTERED_KEY = "stocktalk.entered";
  const APP_URL = "/app?from_landing=1";

  if (localStorage.getItem(ENTERED_KEY) === "1") {
    window.location.href = APP_URL;
    return;
  }

  function launchApp(promptText) {
    localStorage.setItem(ENTERED_KEY, "1");
    if (promptText) {
      sessionStorage.setItem("stocktalk.pending_prompt", promptText);
    }
    window.location.href = APP_URL;
  }

  const launchBtns = [
    document.getElementById("landing-launch-btn"),
    document.getElementById("hero-launch-btn"),
  ];

  launchBtns.forEach((btn) => {
    btn?.addEventListener("click", () => launchApp());
  });

  const promptChips = document.querySelectorAll(".landing-prompt-chip");
  promptChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const prompt = chip.getAttribute("data-prompt");
      launchApp(prompt);
    });
  });
}

function initIndex() {
  const BASE_CHAIN_ID = window.STOCKTALK?.chainId || 8453;
  const WALLET_KEY = "stocktalk.wallet";
  const BASE_L2_RESOLVER = "0xC6d566A56A1aFf6508b41f6c90ff131615583BCD";

  const homeLinks = document.querySelectorAll('a[href="/"]');
  homeLinks.forEach((link) => {
    link.addEventListener("click", () => {
      localStorage.removeItem("stocktalk.entered");
    });
  });

  const RESOLVER_ABI = [
    "function name(bytes32 node) view returns (string)",
    "function text(bytes32 node, string key) view returns (string)",
  ];
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
  const emptyState = document.getElementById("empty-state");

  let disconnectBtn = document.getElementById("disconnect-btn");
  if (!disconnectBtn && walletBtn?.parentElement) {
    disconnectBtn = document.createElement("button");
    disconnectBtn.id = "disconnect-btn";
    disconnectBtn.type = "button";
    disconnectBtn.className = "disconnect-btn";
    disconnectBtn.textContent = "Disconnect";
    disconnectBtn.hidden = true;
    walletBtn.parentElement.appendChild(disconnectBtn);
  }

  let wallet = localStorage.getItem(WALLET_KEY) || null;
  let walletProfile = { name: null, avatar: null };
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

  function hideEmptyState() {
    if (emptyState) emptyState.style.display = "none";
  }

  function renderMarkdown(text) {
    const esc = String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return esc
      .replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|\n)[-*] (.+)/g, "$1• $2")
      .replace(/\n/g, "<br>");
  }

  function append(role, text, extraClass) {
    hideEmptyState();
    const el = document.createElement("div");
    el.className = `msg ${role}${extraClass ? ` ${extraClass}` : ""}`;
    if (role === "assistant") el.innerHTML = renderMarkdown(text);
    else el.textContent = text;
    logEl.appendChild(el);
    logEl.scrollTop = logEl.scrollHeight;
    return el;
  }

  function appendHtml(node) {
    hideEmptyState();
    logEl.appendChild(node);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function shortAddr(addr) {
    return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
  }

  function hexChain(id) {
    return `0x${Number(id).toString(16)}`;
  }

  function persistWallet(addr) {
    if (addr) localStorage.setItem(WALLET_KEY, addr.toLowerCase());
    else localStorage.removeItem(WALLET_KEY);
  }

  function paintWalletButton() {
    if (!walletBtn) return;
    if (!wallet) {
      walletBtn.classList.remove("connected");
      walletBtn.innerHTML = "Connect wallet";
      if (disconnectBtn) disconnectBtn.hidden = true;
      return;
    }
    walletBtn.classList.add("connected");
    const label = walletProfile.name || shortAddr(wallet);
    const img = walletProfile.avatar
      ? `<img class="wallet-avatar" alt="" src="${walletProfile.avatar}" referrerpolicy="no-referrer">`
      : "";
    walletBtn.innerHTML = `${img}<span>${label}</span>`;
    if (disconnectBtn) disconnectBtn.hidden = false;
  }

  function reverseNode(address, chainId) {
    const addr = address.toLowerCase();
    const addrHash = ethers.solidityPackedKeccak256(["string"], [addr.slice(2)]);
    const coinType = ((0x80000000 | chainId) >>> 0).toString(16).toUpperCase();
    const parent = ethers.namehash(`${coinType}.reverse`);
    return ethers.solidityPackedKeccak256(["bytes32", "bytes32"], [parent, addrHash]);
  }

  function normalizeIpfs(url) {
    if (!url) return "";
    if (url.startsWith("ipfs://")) return "https://ipfs.io/ipfs/" + url.slice(7);
    if (url.startsWith("ipfs/")) return "https://ipfs.io/ipfs/" + url.slice(5);
    return url;
  }

  async function resolveAvatarUrl(name, raw) {
    const url = normalizeIpfs(raw);
    const candidates = [
      url && !url.startsWith("eip155:") ? url : "",
      name ? `https://metadata.ens.domains/mainnet/avatar/${name}` : "",
      name ? `https://metadata.ens.domains/8453/avatar/${name}` : "",
      name ? `https://euc.li/${name}` : "",
    ].filter(Boolean);

    for (const src of candidates) {
      try {
        const res = await fetch(src, { method: "HEAD" });
        const type = (res.headers.get("content-type") || "").toLowerCase();
        if (res.ok && (type.startsWith("image/") || type.includes("octet-stream") || !type)) {
          return src;
        }
        if (res.ok && type.startsWith("application/json")) continue;
        if (res.ok) return src;
      } catch (_err) {}
    }
    return url && !url.startsWith("eip155:") ? url : null;
  }

  async function resolveIdentity(address) {
    walletProfile = { name: null, avatar: null };
    try {
      const baseProvider = new ethers.JsonRpcProvider("https://mainnet.base.org");
      const resolver = new ethers.Contract(BASE_L2_RESOLVER, RESOLVER_ABI, baseProvider);
      const basename = await resolver.name(reverseNode(address, 8453));
      if (basename) {
        walletProfile.name = basename;
        try {
          const node = ethers.namehash(basename);
          const avatar = await resolver.text(node, "avatar");
          walletProfile.avatar = await resolveAvatarUrl(basename, avatar);
        } catch (_err) {
          walletProfile.avatar = await resolveAvatarUrl(basename, "");
        }
      }
    } catch (_err) {}

    if (!walletProfile.name) {
      try {
        const ethProvider = new ethers.JsonRpcProvider("https://eth.llamarpc.com");
        const ens = await ethProvider.lookupAddress(address);
        if (ens) {
          walletProfile.name = ens;
          try {
            const ensAvatar = await ethProvider.getAvatar(ens);
            walletProfile.avatar = await resolveAvatarUrl(ens, ensAvatar || "");
          } catch (_err) {
            walletProfile.avatar = await resolveAvatarUrl(ens, "");
          }
        }
      } catch (_err) {}
    }

    if (!walletProfile.name || !walletProfile.avatar) {
      try {
        const res = await fetch(`https://ensdata.net/${address}`);
        if (res.ok) {
          const data = await res.json();
          walletProfile.name = walletProfile.name || data.name || data.ens || null;
          const raw = data.avatar || data.avatar_url || "";
          walletProfile.avatar =
            walletProfile.avatar || (await resolveAvatarUrl(walletProfile.name, raw));
        }
      } catch (_err) {}
    }

    if (walletProfile.name && !walletProfile.avatar) {
      walletProfile.avatar = await resolveAvatarUrl(walletProfile.name, "");
    }

    paintWalletButton();
  }

  async function setWallet(addr, { persist = true } = {}) {
    wallet = addr || null;
    walletProfile = { name: null, avatar: null };
    if (persist) persistWallet(wallet);
    paintWalletButton();
    if (wallet) resolveIdentity(wallet);
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

  async function connectWallet({ request = true } = {}) {
    if (!window.ethereum) {
      append("assistant", "No injected wallet. Install MetaMask and refresh.", "error");
      return;
    }
    await ensureBase();
    const method = request ? "eth_requestAccounts" : "eth_accounts";
    const accounts = await window.ethereum.request({ method });
    const addr = accounts?.[0] || null;
    if (!addr) {
      await setWallet(null);
      if (request) append("assistant", "No account returned by the wallet.", "error");
      return;
    }
    await setWallet(addr);
    if (!tokens.length) await loadTokens();
  }

  function disconnectWallet() {
    setWallet(null);
    conversationId = null;
  }

  walletBtn.addEventListener("click", () => {
    connectWallet({ request: true }).catch((err) =>
      append("assistant", err.message || String(err), "error")
    );
  });

  disconnectBtn?.addEventListener("click", () => {
    disconnectWallet();
    append("assistant", "Wallet disconnected.");
  });

  if (window.ethereum) {
    window.ethereum.on?.("accountsChanged", (accounts) => {
      const next = accounts?.[0] || null;
      if (next) setWallet(next);
      else disconnectWallet();
    });
    window.ethereum.on?.("chainChanged", () => window.location.reload());
  }

  function renderQuoteCard(action) {
    const card = document.createElement("div");
    card.className = "quote-card";
    const mock = Boolean(action.mock) || action.route === "MOCK";
    const canConfirm = !mock || demoEnabled();
    const isLp = action.type === "tx";
    const title = isLp ? action.summary || "Confirm on Base" : "Confirm swap on Base";
    const fromLabel = action.from ? `${action.from.amount} ${action.from.symbol}` : "—";
    const toLabel = action.to ? `${action.to.amount} ${action.to.symbol}` : "—";
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
    if (!wallet) await connectWallet({ request: true });

    const provider = new ethers.BrowserProvider(window.ethereum);
    const signer = await provider.getSigner();
    const from = await signer.getAddress();
    await setWallet(from);

    const spender = action.spender;
    if (!spender) throw new Error("Quote is missing a spender.");
    if (!action.tx?.to || !action.tx?.data) throw new Error("Quote is missing transaction data.");

    const skipApprove = ["aave_borrow", "aave_collateral", "aave_withdraw", "uni_lp_remove", "slip_lp_remove"].includes(action.kind);
    const approvals = skipApprove
      ? []
      : (action.approvals && action.approvals.length
          ? action.approvals
          : [{ address: action.from.address, amountWei: action.from.amountWei, symbol: action.from.symbol }]);

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
      rememberToken({ symbol: "AERO-LP", address: action.raw.pool, decimals: 18 });
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
    if (sendBtn) sendBtn.disabled = true;
    const status = append("assistant", "Thinking…", "thinking");
    const slow = setTimeout(() => {
      if (status.isConnected) status.textContent = "Still thinking…";
    }, 5000);
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
        status.textContent = data.error || "Chat failed";
        status.classList.add("error");
        return;
      }
      conversationId = data.conversation_id;
      status.innerHTML = renderMarkdown(data.message || "");
      status.classList.remove("thinking");
      if (!data.message) status.remove();
      if (data.action?.type === "quote" || data.action?.type === "tx") {
        if (data.action.raw?.pool) {
          rememberToken({ symbol: "AERO-LP", address: data.action.raw.pool, decimals: 18 });
        }
        renderQuoteCard(data.action);
      }
    } catch (err) {
      status.textContent = err.message || String(err);
      status.classList.add("error");
    } finally {
      clearTimeout(slow);
      if (sendBtn) sendBtn.disabled = false;
    }
  }

  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    sendChat(text);
  });

  const promptButtons = document.querySelectorAll(".empty-chip, .rail-prompt-btn");
  promptButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const promptText = btn.getAttribute("data-prompt");
      if (promptText) {
        input.value = promptText;
        sendChat(promptText);
        input.value = "";
      }
    });
  });

  (async function boot() {
    paintWalletButton();
    await loadTokens().catch(() => {});
    if (localStorage.getItem(WALLET_KEY) && window.ethereum) {
      try {
        await connectWallet({ request: false });
      } catch (_err) {
        persistWallet(null);
      }
    }
    const pending = sessionStorage.getItem("stocktalk.pending_prompt");
    if (pending) {
      sessionStorage.removeItem("stocktalk.pending_prompt");
      await sendChat(pending);
    }
  })();
}