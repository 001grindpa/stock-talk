document.addEventListener("DOMContentLoaded", () => {
  const pageId = document.body.id;
  const pageLoader = document.querySelector(".page-loader");

  window.addEventListener("load", () => {
    pageLoader?.classList.add("is-hidden");
  }, { once: true });

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
  const ATTESTATION_KEY = "stocktalk.attest.non_us";
  const attestationOverlay = document.getElementById("attestation-overlay");
  const attestationPanel = attestationOverlay?.querySelector(".attestation-panel");
  const attestationCheckbox = document.getElementById("attestation-checkbox");
  const attestationContinue = document.getElementById("attestation-continue");

  function hideAttestation() {
    if (!attestationOverlay) return;
    attestationOverlay.hidden = true;
    attestationOverlay.setAttribute("aria-hidden", "true");
  }

  function showAttestation() {
    if (!attestationOverlay) return;
    attestationOverlay.hidden = false;
    attestationOverlay.removeAttribute("aria-hidden");
    attestationCheckbox?.focus();
  }

  if (localStorage.getItem(ATTESTATION_KEY) === "1") {
    hideAttestation();
  } else {
    showAttestation();
  }

  attestationCheckbox?.addEventListener("change", () => {
    if (attestationContinue) attestationContinue.disabled = !attestationCheckbox.checked;
  });

  attestationContinue?.addEventListener("click", () => {
    if (!attestationCheckbox?.checked) return;
    localStorage.setItem(ATTESTATION_KEY, "1");
    hideAttestation();
  });

  attestationOverlay?.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      return;
    }
    if (event.key !== "Tab" || !attestationPanel) return;
    const focusable = attestationPanel.querySelectorAll(
      "button:not(:disabled), input:not(:disabled)"
    );
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  const BASE_CHAIN_ID = window.STOCKTALK?.chainId || 8453;
  const WALLET_KEY = "stocktalk.wallet";
  const BASE_L2_RESOLVER = "0xC6d566A56A1aFf6508b41f6c90ff131615583BCD";
  const BASE_RPC_URL = window.STOCKTALK?.baseRpcUrl || "https://mainnet.base.org";
  const baseJsonProvider = new ethers.JsonRpcProvider(BASE_RPC_URL);
  const ETH_RPC_URL = window.STOCKTALK?.ethRpcUrl || "https://ethereum.publicnode.com";
  const ethJsonProvider = new ethers.JsonRpcProvider(ETH_RPC_URL);
  const identityCache = new Map();
  const NATIVE_ETH = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";

  const BUILDER_CODE = "bc_s8ik8jmd";

  function isNative(addr) {
    const a = String(addr || "").toLowerCase();
    return a === NATIVE_ETH || a === "0x0000000000000000000000000000000000000000";
  }

  function withBuilderSuffix(data) {
    const code = String(BUILDER_CODE || "").trim();
    if (!code) return data;
    const body = String(data || "0x").replace(/^0x/i, "");
    const codeHex = ethers.hexlify(ethers.toUtf8Bytes(code)).slice(2);
    const len = (codeHex.length / 2).toString(16).padStart(2, "0");
    const marker = "80218021802180218021802180218021";
    return "0x" + body + codeHex + len + "00" + marker;
  }

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

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
  const walletCopyPopup = document.getElementById("wallet-copy-popup");
  const copyWalletAddress = document.getElementById("copy-wallet-address");
  const copyToast = document.getElementById("copy-toast");
  const emptyState = document.getElementById("empty-state");
  const historyToggle = document.getElementById("history-toggle");
  const historyMobilePanel = document.getElementById("history-mobile-panel");
  const historyBackdrop = document.getElementById("history-backdrop");
  const historyClose = document.getElementById("history-close");
  const historyStatuses = document.querySelectorAll("[data-history-status]");
  const historyLists = document.querySelectorAll("[data-history-list]");

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
  let signedIn = false;
  let isConnecting = false;
  let connectingAddress = null;
  let pendingConnectPrompt = null;
  let walletProfile = { name: null, avatar: null };
  let tokens = [];
  let extraTokens = [];
  let tradeHistory = [];
  let copyToastTimer;
  const threadId =
    (window.crypto && crypto.randomUUID && crypto.randomUUID()) ||
    `session-${Date.now()}`;

  function sessionThread() {
    return threadId;
  }

  function landingPromptText(prompt) {
    return prompt;
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
      .replace(/(^|\W)\*([^*\n]+)\*(?=\W|$)/g, "$1<em>$2</em>")
      .replace(/(^|\W)_([^_\n]+)_(?=\W|$)/g, "$1<em>$2</em>")
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

  function relativeTime(value) {
    if (!value) return "";
    const parsed = new Date(value.endsWith("Z") ? value : `${value}Z`);
    if (Number.isNaN(parsed.getTime())) return "";
    const seconds = Math.round((Date.now() - parsed.getTime()) / 1000);
    const units = [
      [60, "second"],
      [3600, "minute"],
      [86400, "hour"],
      [604800, "day"],
      [2592000, "week"],
      [31536000, "month"],
    ];
    let amount = seconds;
    let unit = "second";
    for (const [limit, name] of units) {
      if (Math.abs(seconds) < limit) break;
      amount = Math.round(seconds / limit);
      unit = name;
    }
    return `${Math.abs(amount)} ${unit}${Math.abs(amount) === 1 ? "" : "s"} ago`;
  }

  function shortHash(hash) {
    return hash ? `${hash.slice(0, 8)}…${hash.slice(-6)}` : "Unknown transaction";
  }

  function renderHistory() {
    const connected = Boolean(wallet && signedIn);
    if (historyToggle) historyToggle.hidden = false;
    if (!connected) closeHistory();
    historyStatuses.forEach((status) => {
      status.textContent = connected
        ? tradeHistory.length
          ? ""
          : "No trades yet."
        : "Connect a wallet to see trade history.";
      status.hidden = connected && tradeHistory.length > 0;
    });
    historyLists.forEach((list) => {
      list.replaceChildren();
      list.hidden = !connected || tradeHistory.length === 0;
      tradeHistory.forEach((trade) => {
        const item = document.createElement("li");
        item.className = "history-item";

        const details = document.createElement("div");
        details.className = "history-details";
        const kind = document.createElement("strong");
        kind.textContent = trade.kind || "Trade";
        const route = document.createElement("span");
        route.textContent = trade.route || "Base";
        const kindRow = document.createElement("div");
        kindRow.className = "history-kind";
        kindRow.append(kind, route);

        const pair = document.createElement("div");
        pair.className = "history-pair";
        const fromAmt = [trade.from_amount, trade.from_symbol].filter(Boolean).join(" ");
        const toAmt = [trade.to_amount, trade.to_symbol].filter(Boolean).join(" ");
        pair.textContent = fromAmt && toAmt ? `${fromAmt} → ${toAmt}` : fromAmt || toAmt || "Transaction submitted";

        const hash = document.createElement("div");
        hash.className = "history-hash";
        hash.textContent = `${shortHash(trade.tx_hash)} · ${relativeTime(trade.created_at)}`;
        details.append(kindRow, pair, hash);

        const link = document.createElement("a");
        link.className = "history-link";
        link.textContent = "View on Basescan";
        link.href = trade.explorer || `https://basescan.org/tx/${trade.tx_hash}`;
        link.target = "_blank";
        link.rel = "noopener";
        item.append(details, link);
        list.append(item);
      });
    });
  }

  function openHistory() {
    historyMobilePanel?.classList.add("is-open");
    historyBackdrop?.classList.add("is-visible");
    historyMobilePanel?.setAttribute("aria-hidden", "false");
    historyBackdrop?.setAttribute("aria-hidden", "false");
    historyToggle?.setAttribute("aria-expanded", "true");
    historyToggle?.setAttribute("aria-label", "Close trade history");
    document.body.classList.add("history-drawer-open");
  }

  function closeHistory() {
    if (!historyMobilePanel || !historyBackdrop) return;
    historyMobilePanel.classList.remove("is-open");
    historyBackdrop.classList.remove("is-visible");
    historyMobilePanel.setAttribute("aria-hidden", "true");
    historyBackdrop.setAttribute("aria-hidden", "true");
    historyToggle?.setAttribute("aria-expanded", "false");
    historyToggle?.setAttribute("aria-label", "Open trade history");
    document.body.classList.remove("history-drawer-open");
  }

  async function loadTradeHistory(address = wallet) {
    if (!address) {
      tradeHistory = [];
      renderHistory();
      return;
    }
    const res = await fetch(`/api/trades?wallet=${encodeURIComponent(address)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not load trade history.");
    tradeHistory = data.trades || [];
    renderHistory();
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

  function getInjectedProvider() {
    const list = [];
    if (Array.isArray(window.ethereum?.providers)) list.push(...window.ethereum.providers);
    if (window.ethereum) list.push(window.ethereum);
    if (window.coinbaseWalletExtension) list.push(window.coinbaseWalletExtension);
    return (
      list.find((p) => p?.isMetaMask && !p?.isBraveWallet) ||
      list.find((p) => p?.isCoinbaseWallet || p?.isCoinbaseBrowser) ||
      list.find((p) => p?.isRabby) ||
      list.find((p) => typeof p?.request === "function") ||
      window.ethereum ||
      null
    );
  }

  async function readChainId(eth) {
    try {
      const id = await eth.request({ method: "eth_chainId" });
      return parseInt(id, 16);
    } catch (_err) {
      try {
        const id = await eth.request({ method: "net_version" });
        return parseInt(id, 10);
      } catch (_err2) {
        const raw = eth.chainId || eth.networkVersion;
        if (raw == null) {
          throw new Error(
            "This injected wallet does not expose chain id. Enable MetaMask or Coinbase Wallet for this site."
          );
        }
        return typeof raw === "string" && raw.startsWith("0x")
          ? parseInt(raw, 16)
          : parseInt(raw, 10);
      }
    }
  }

  function paintWalletButton() {
    if (!walletBtn) return;
    if (!wallet || !signedIn) {
      walletBtn.classList.remove("connected");
      walletBtn.innerHTML = "Connect wallet";
      if (disconnectBtn) disconnectBtn.hidden = true;
      if (walletCopyPopup) walletCopyPopup.hidden = true;
      return;
    }
    walletBtn.classList.add("connected");
    const label = walletProfile.name || shortAddr(wallet);
    const img = walletProfile.avatar
      ? `<img class="wallet-avatar" alt="" src="${walletProfile.avatar}" onerror="this.style.display='none'" referrerpolicy="no-referrer">`
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

  function normalizeAvatarUrl(url) {
    if (!url) return null;
    const trimmed = String(url).trim();
    if (trimmed.startsWith("ipfs://")) return "https://ipfs.io/ipfs/" + trimmed.slice(7);
    if (trimmed.startsWith("ipfs/")) return "https://ipfs.io/ipfs/" + trimmed.slice(5);
    if (/^(Qm[1-9A-HJ-NP-Za-km-z]{44}|bafy[a-z0-9]+)/i.test(trimmed)) {
      return "https://ipfs.io/ipfs/" + trimmed;
    }
    if (trimmed.startsWith("ar://")) return "https://arweave.net/" + trimmed.slice(5);
    if (trimmed.startsWith("arweave:")) return "https://arweave.net/" + trimmed.slice(8);
    if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) return trimmed;
    if (trimmed.startsWith("data:image/")) return trimmed;
    return null;
  }

  function getAvatarUrl(name, raw) {
    const direct = normalizeAvatarUrl(raw);
    if (direct) return direct;
    if (name && name.endsWith(".eth") && !name.endsWith(".base.eth")) {
      return `https://metadata.ens.domains/mainnet/avatar/${name}`;
    }
    return null;
  }

  async function resolveIdentity(address) {
    if (!address) return;
    const addr = address.toLowerCase();

    if (identityCache.has(addr)) {
      walletProfile = { ...identityCache.get(addr) };
      paintWalletButton();
      return;
    }

    walletProfile = { name: null, avatar: null };

    try {
      const resolver = new ethers.Contract(BASE_L2_RESOLVER, RESOLVER_ABI, baseJsonProvider);
      const basename = await resolver.name(reverseNode(addr, 8453)).catch(() => null);

      if (basename) {
        walletProfile.name = basename;
        paintWalletButton();

        try {
          const node = ethers.namehash(basename);
          const avatarRecord = await resolver.text(node, "avatar").catch(() => "");
          walletProfile.avatar = getAvatarUrl(basename, avatarRecord);
        } catch (_err) {
          walletProfile.avatar = null;
        }

        // If Basename avatar is not available, check if user has an ENS name avatar on Ethereum mainnet
        if (!walletProfile.avatar) {
          try {
            const ens = await ethJsonProvider.lookupAddress(addr).catch(() => null);
            if (ens) {
              const ensAvatar = await ethJsonProvider.getAvatar(ens).catch(() => null);
              walletProfile.avatar = getAvatarUrl(ens, ensAvatar || "") || (ens.endsWith(".eth") ? `https://metadata.ens.domains/mainnet/avatar/${ens}` : null);
            }
          } catch (_err) {}
        }

        identityCache.set(addr, { ...walletProfile });
        paintWalletButton();
        return;
      }
    } catch (_err) {}

    try {
      const ens = await ethJsonProvider.lookupAddress(addr).catch(() => null);
      if (ens) {
        walletProfile.name = ens;
        paintWalletButton();
        try {
          const ensAvatar = await ethJsonProvider.getAvatar(ens).catch(() => null);
          walletProfile.avatar = getAvatarUrl(ens, ensAvatar || "") || (ens.endsWith(".eth") ? `https://metadata.ens.domains/mainnet/avatar/${ens}` : null);
        } catch (_e) {
          walletProfile.avatar = ens.endsWith(".eth") ? `https://metadata.ens.domains/mainnet/avatar/${ens}` : null;
        }
        identityCache.set(addr, { ...walletProfile });
        paintWalletButton();
        return;
      }
    } catch (_err) {}

    identityCache.set(addr, { ...walletProfile });
    paintWalletButton();
  }

  async function setWallet(addr, { persist = true } = {}) {
    wallet = addr ? addr.toLowerCase() : null;
    walletProfile = { name: null, avatar: null };
    if (persist) persistWallet(wallet);
    paintWalletButton();
    if (wallet) {
      resolveIdentity(wallet);
      await loadTradeHistory(wallet);
    } else {
      tradeHistory = [];
      renderHistory();
    }
  }

  function rememberToken(token) {
    if (!token?.address || isNative(token.address)) return;
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
    const eth = getInjectedProvider();
    if (!wallet || !eth) return [];
    const provider = new ethers.BrowserProvider(eth);
    const list = [...tokens, ...extraTokens];
    const out = [];
    try {
      const native = await provider.getBalance(wallet);
      out.push({
        symbol: "ETH",
        address: "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
        decimals: 18,
        raw: native.toString(),
        formatted: ethers.formatEther(native),
      });
    } catch (_err) {}
    for (const token of list) {
      if (isNative(token.address) || (token.symbol || "").toUpperCase() === "ETH") continue;
      try {
        const contract = new ethers.Contract(token.address, ERC20_ABI, provider);
        let decimals = Number(token.decimals);
        try {
          const chainDecimals = Number(await contract.decimals());
          if (Number.isFinite(chainDecimals)) decimals = chainDecimals;
        } catch (_err) {}
        const raw = await contract.balanceOf(wallet);
        out.push({
          symbol: token.symbol,
          address: token.address,
          decimals,
          raw: raw.toString(),
          formatted: ethers.formatUnits(raw, decimals),
        });
      } catch (_err) {}
    }
    return out;
  }

  async function ensureBase() {
    const eth = getInjectedProvider();
    if (!eth) {
      throw new Error("No browser wallet found. Install MetaMask or a Base-compatible wallet.");
    }
    window.ethereum = eth;
    const chainId = await readChainId(eth);
    if (chainId === BASE_CHAIN_ID) return;
    try {
      await eth.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: hexChain(BASE_CHAIN_ID) }],
      });
    } catch (err) {
      if (err?.code === 4902 || /unrecognized|not added/i.test(err?.message || "")) {
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

  async function connectWallet({ request = true, replay = false } = {}) {
    if (isConnecting) return;
    isConnecting = true;
    try {
      const eth = getInjectedProvider();
      if (!eth) {
        if (request) append("assistant", "No injected wallet. Install MetaMask/Coinbase wallet and refresh.", "error");
        return;
      }
      window.ethereum = eth;
      await ensureBase();
      const method = request ? "eth_requestAccounts" : "eth_accounts";
      let accounts;
      try {
        accounts = await eth.request({ method });
      } catch (err) {
        if (request) append("assistant", err?.message || "Wallet connection request was rejected.", "error");
        return;
      }
      const addr = accounts?.[0] || null;
      if (!addr) {
        await setWallet(null);
        signedIn = false;
        if (request) append("assistant", "No account returned by the wallet.", "error");
        return;
      }

      const normalized = addr.toLowerCase();
      connectingAddress = normalized;

      // Check existing server session
      try {
        const meRes = await fetch("/api/auth/me");
        if (meRes.ok) {
          const meData = await meRes.json();
          if (meData.wallet && meData.wallet.toLowerCase() === normalized) {
            signedIn = true;
            await setWallet(addr);
            if (!tokens.length) await loadTokens();
            if (replay) {
              const retry = pendingConnectPrompt;
              pendingConnectPrompt = null;
              if (retry) sendChat(retry);
            }
            return;
          }
        }
      } catch (_err) {}

      // No valid session on server for this address: prompt sign-in
      try {
        const nonceRes = await fetch("/api/auth/nonce", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ wallet: addr }),
        });
        if (!nonceRes.ok) {
          const errJson = await nonceRes.json().catch(() => ({}));
          throw new Error(errJson.error || "Failed to generate sign-in nonce.");
        }
        const { message } = await nonceRes.json();

        const provider = new ethers.BrowserProvider(eth);
        const signer = await provider.getSigner();
        const signature = await signer.signMessage(message);

        const verifyRes = await fetch("/api/auth/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ wallet: addr, message, signature }),
        });
        const verifyJson = await verifyRes.json().catch(() => ({}));
        if (!verifyRes.ok || !verifyJson.ok) {
          throw new Error(verifyJson.error || "Failed to verify signature.");
        }

        signedIn = true;
        await setWallet(addr);
        if (!tokens.length) await loadTokens();

        if (replay) {
          const retry = pendingConnectPrompt;
          pendingConnectPrompt = null;
          if (retry) sendChat(retry);
        }
      } catch (err) {
        console.error("Sign-in failed or rejected:", err);
        await setWallet(null);
        signedIn = false;
        await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
        append("assistant", "Sign-in cancelled. Connect again and sign the login message.");
      }
    } finally {
      isConnecting = false;
      connectingAddress = null;
    }
  }

  async function disconnectWallet() {
    signedIn = false;
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    await setWallet(null);
  }

  walletBtn.addEventListener("click", () => {
    if (wallet && signedIn) {
      if (walletCopyPopup) walletCopyPopup.hidden = !walletCopyPopup.hidden;
      return;
    }
    connectWallet({ request: true, replay: true }).catch((err) =>
      append("assistant", err.message || String(err), "error")
    );
  });

  copyWalletAddress?.addEventListener("click", async () => {
    if (!wallet) return;
    try {
      await navigator.clipboard.writeText(wallet);
      if (walletCopyPopup) walletCopyPopup.hidden = true;
      copyToast?.classList.add("is-visible");
      clearTimeout(copyToastTimer);
      copyToastTimer = setTimeout(() => copyToast?.classList.remove("is-visible"), 2200);
    } catch (_err) {}
  });

  document.addEventListener("click", (event) => {
    if (
      walletCopyPopup &&
      !walletCopyPopup.hidden &&
      !walletCopyPopup.contains(event.target) &&
      !walletBtn.contains(event.target)
    ) {
      walletCopyPopup.hidden = true;
    }
  });

  disconnectBtn?.addEventListener("click", async () => {
    await disconnectWallet();
    append("assistant", "Wallet disconnected.");
  });

  const liveEth = getInjectedProvider();
  if (liveEth) {
    liveEth.on?.("accountsChanged", async (accounts) => {
      const next = accounts?.[0] || null;
      if (!next) {
        await disconnectWallet();
        return;
      }
      const nextNorm = next.toLowerCase();
      if (wallet && nextNorm === wallet.toLowerCase() && signedIn) {
        return;
      }
      if (isConnecting && (!connectingAddress || nextNorm === connectingAddress)) {
        // Connection & sign-in already in progress for this address
        return;
      }
      signedIn = false;
      await connectWallet({ request: false, replay: false });
    });
    liveEth.on?.("chainChanged", () => window.location.reload());
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

  function renderBasketCard(basket) {
    const card = document.createElement("div");
    card.className = "quote-card basket-card";
    const legs = basket.legs || [];
    const ready = legs.filter((l) => l.ok);
    const rows = legs
      .map((leg) => {
        if (!leg.ok) {
          return `<div class="quote-row error"><span>${esc(leg.symbol || "?")}</span><span>${esc(leg.error || "no route")}</span></div>`;
        }
        return `<div class="quote-row">
          <span>${esc(leg.from.amount)} ${esc(leg.from.symbol)}</span>
          <span>→ ${esc(leg.to.amount)} ${esc(leg.to.symbol)}</span>
          <span class="muted">${esc(leg.route || "")}${leg.note ? " · " + esc(leg.note) : ""}</span>
        </div>`;
      })
      .join("");

    card.innerHTML = `
      <div class="quote-title">Basket on Base · ${ready.length}/${legs.length} ready</div>
      <p class="muted">${esc(basket.summary || "")}</p>
      ${rows}
      <div class="confirm-actions">
        <button type="button" class="confirm" ${ready.length ? "" : "disabled"}>Confirm next swap</button>
        <button type="button" class="cancel">Cancel</button>
      </div>
    `;
    appendHtml(card);

    const confirmBtn = card.querySelector(".confirm");
    const cancelBtn = card.querySelector(".cancel");
    cancelBtn.addEventListener("click", () => {
      confirmBtn.disabled = true;
      cancelBtn.disabled = true;
      append("assistant", "Basket cancelled.");
    });
    confirmBtn.addEventListener("click", () => {
      executeBasket(ready, confirmBtn, cancelBtn).catch((err) => {
        append("assistant", err?.shortMessage || err?.message || String(err), "error");
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
      });
    });
  }

  async function executeBasket(legs, confirmBtn, cancelBtn) {
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;
    for (let i = 0; i < legs.length; i += 1) {
      const leg = legs[i];
      append(
        "assistant",
        `Swap ${i + 1}/${legs.length}: ${leg.from.symbol} → ${leg.to.symbol}. Confirm in your wallet.`
      );
      try {
        await executeQuote(leg, confirmBtn, cancelBtn);
      } catch (err) {
        append(
          "assistant",
          `Leg ${i + 1} failed: ${err.message || err}. Remaining legs were not sent.`,
          "error"
        );
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
        return;
      }
    }
    append("assistant", "Basket complete.");
  }

  const ADDR_RE = /^0x[a-fA-F0-9]{40}$/;
  const FORWARD_RESOLVER_ABI = [
    "function addr(bytes32 node) view returns (address)",
  ];

  function isHexAddress(value) {
    return ADDR_RE.test(String(value || "").trim());
  }

  async function resolveRecipient(raw) {
    const text = String(raw || "").trim();
    if (!text) return { address: "", label: "" };
    if (isHexAddress(text)) {
      return { address: text.toLowerCase(), label: text };
    }
    const name = text.endsWith(".base.eth") || text.includes(".") ? text : `${text}.base.eth`;
    const resolver = new ethers.Contract(BASE_L2_RESOLVER, FORWARD_RESOLVER_ABI, baseJsonProvider);
    const node = ethers.namehash(name);
    const address = await resolver.addr(node);
    if (!address || address === ethers.ZeroAddress) {
      throw new Error(`Could not resolve ${name}`);
    }
    return { address: address.toLowerCase(), label: name };
  }

  async function loadStockOptions() {
    const res = await fetch("/api/tokens");
    const data = await res.json();
    return (data.tokens || []).filter((t) => t.kind === "stock");
  }

  function renderGiftCard(action) {
    const card = document.createElement("div");
    card.className = "quote-card gift-card";
    const preSymbol = String(action.symbol || "").toUpperCase();
    const presetFrac = Number(action.fraction || 0);
    card.innerHTML = `
      <h3>Gift a tokenized stock</h3>
      <label class="gift-field">
        <span>Stock</span>
        <select class="gift-symbol"></select>
      </label>
      <label class="gift-field">
        <span>Amount</span>
        <input class="gift-amount" type="text" inputmode="decimal" placeholder="0.01" value="${esc(presetFrac ? "" : action.amount || "")}">
        <small class="gift-balance muted">Balance: —</small>
        <div class="gift-presets">
          <button type="button" class="gift-preset" data-frac="0.25">25%</button>
          <button type="button" class="gift-preset" data-frac="0.5">50%</button>
          <button type="button" class="gift-preset" data-frac="0.75">75%</button>
          <button type="button" class="gift-preset" data-frac="1">100%</button>
        </div>
      </label>
      <label class="gift-field">
        <span>Recipient</span>
        <input class="gift-to" type="text" placeholder="0x… or name.base.eth" value="${esc(action.to || "")}">
        <small class="gift-resolved muted"></small>
      </label>
      <label class="gift-field">
        <span>Memo (optional)</span>
        <input class="gift-memo" type="text" maxlength="32" placeholder="optional note" value="${esc(action.memo || "")}">
      </label>
      <div class="confirm-actions">
        <button type="button" class="confirm" disabled>Gift</button>
        <button type="button" class="cancel">Cancel</button>
      </div>
    `;
    appendHtml(card);

    const symbolEl = card.querySelector(".gift-symbol");
    const amountEl = card.querySelector(".gift-amount");
    const toEl = card.querySelector(".gift-to");
    const memoEl = card.querySelector(".gift-memo");
    const resolvedEl = card.querySelector(".gift-resolved");
    const balanceEl = card.querySelector(".gift-balance");
    const confirmBtn = card.querySelector(".confirm");
    const cancelBtn = card.querySelector(".cancel");
    let resolvedTo = isHexAddress(action.to) ? action.to.toLowerCase() : "";
    let stockBalances = [];

    function tokenAliases(token) {
      const raw = token.aliases;
      if (Array.isArray(raw)) return raw;
      if (typeof raw === "string" && raw.trim()) {
        try {
          const parsed = JSON.parse(raw);
          return Array.isArray(parsed) ? parsed : [];
        } catch (_err) {
          return [];
        }
      }
      return [];
    }

    function refreshGiftButton() {
      const ready = Boolean(symbolEl.value && Number(amountEl.value) > 0 && resolvedTo);
      confirmBtn.disabled = !ready;
    }

    function selectedBalance() {
      const symbol = (symbolEl.value || "").toUpperCase();
      const row = stockBalances.find((b) => (b.symbol || "").toUpperCase() === symbol);
      return row ? Number(row.formatted || 0) : 0;
    }

    function renderBalance() {
      if (!symbolEl.value) {
        balanceEl.textContent = "Balance: —";
        return;
      }
      const bal = selectedBalance();
      balanceEl.textContent = `Balance: ${bal || 0} ${symbolEl.value}`;
    }

    function fillPercent(frac) {
      const bal = selectedBalance();
      if (!symbolEl.value || !(bal > 0)) return;
      amountEl.value = (bal * frac).toFixed(8).replace(/\.?0+$/, "");
      refreshGiftButton();
    }

    function populateSelect(tokenList) {
      symbolEl.innerHTML =
        `<option value="">Select stock</option>` +
        tokenList
          .map((t) => {
            const names = [t.symbol, t.name, ...tokenAliases(t)].map((s) => String(s).toUpperCase());
            const selected = preSymbol && names.includes(preSymbol) ? "selected" : "";
            return `<option value="${esc(t.symbol)}" ${selected}>${esc(t.symbol)} · ${esc(t.name)}</option>`;
          })
          .join("");
    }

    async function lookupRecipient() {
      resolvedTo = "";
      resolvedEl.textContent = "";
      refreshGiftButton();
      const raw = toEl.value.trim();
      if (!raw) return;
      try {
        if (!isHexAddress(raw)) resolvedEl.textContent = "Resolving Basename…";
        const found = await resolveRecipient(raw);
        resolvedTo = found.address;
        resolvedEl.textContent = isHexAddress(raw)
          ? ""
          : `${found.label} → ${found.address.slice(0, 6)}…${found.address.slice(-4)}`;
      } catch (err) {
        resolvedEl.textContent = err.message || "Could not resolve recipient.";
      }
      refreshGiftButton();
    }

    Promise.all([loadStockOptions(), readBalances()])
      .then(([tokenList, rows]) => {
        stockBalances = rows || [];
        populateSelect(tokenList || []);
        renderBalance();
        if (presetFrac > 0) fillPercent(presetFrac);
        refreshGiftButton();
      })
      .catch(() => {
        balanceEl.textContent = "Balance: unavailable";
        resolvedEl.textContent = resolvedEl.textContent || "Could not load stock list.";
      });

    amountEl.addEventListener("input", refreshGiftButton);
    symbolEl.addEventListener("change", () => {
      renderBalance();
      refreshGiftButton();
    });
    toEl.addEventListener("change", lookupRecipient);
    toEl.addEventListener("blur", lookupRecipient);
    if (action.to) lookupRecipient();

    card.querySelectorAll(".gift-preset").forEach((btn) => {
      btn.addEventListener("click", () => fillPercent(Number(btn.dataset.frac)));
    });

    cancelBtn.addEventListener("click", () => {
      confirmBtn.disabled = true;
      cancelBtn.disabled = true;
      append("assistant", "Gift cancelled.");
    });

    confirmBtn.addEventListener("click", () => {
      submitGiftCard(
        {
          symbol: symbolEl.value,
          amount: amountEl.value.trim(),
          to: resolvedTo,
          memo: memoEl.value.trim(),
        },
        confirmBtn,
        cancelBtn
      ).catch((err) => {
        append("assistant", err?.shortMessage || err?.message || String(err), "error");
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
      });
    });
  }

  async function submitGiftCard(fields, confirmBtn, cancelBtn) {
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;
    if (!wallet || !signedIn) {
      await connectWallet({ request: true, replay: false });
      if (!signedIn) {
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
        throw new Error("Sign in with your wallet first.");
      }
    }
    const res = await fetch("/api/gift/build", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        wallet,
        to: fields.to,
        symbol: fields.symbol,
        amount: fields.amount,
        memo: fields.memo,
      }),
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || "Could not build gift.");
    await executeQuote(data, confirmBtn, cancelBtn);
  }

  async function executeQuote(action, confirmBtn, cancelBtn) {
    const eth = getInjectedProvider();
    if (!eth) throw new Error("Connect a wallet first.");
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;

    await ensureBase();
    if (!wallet || !signedIn) {
      await connectWallet({ request: true, replay: false });
      if (!signedIn) {
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
        throw new Error("Sign in with your wallet first.");
      }
    }

    const provider = new ethers.BrowserProvider(eth);
    const signer = await provider.getSigner();
    const from = await signer.getAddress();
    if (from.toLowerCase() !== wallet.toLowerCase()) {
      await setWallet(from);
      signedIn = false;
      await connectWallet({ request: true, replay: false });
      if (!signedIn) {
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
        throw new Error("Sign in with your wallet first.");
      }
    }

    const isGift = action.kind === "gift_transfer" || action.type === "gift";
    const spender = action.spender;
    if (!action.tx?.to || !action.tx?.data) throw new Error("Quote is missing transaction data.");
    if (!isGift && !spender) throw new Error("Quote is missing a spender.");

    const sellingNative = isNative(action.from?.address);
    const skipApprove = isGift || sellingNative || [
      "aave_borrow",
      "aave_collateral",
      "aave_withdraw",
      "morpho_borrow",
      "morpho_withdraw",
      "uni_lp_remove",
      "slip_lp_remove",
    ].includes(action.kind);

    const approvals = skipApprove
      ? []
      : action.approvals && action.approvals.length
        ? action.approvals
        : [{ address: action.from.address, amountWei: action.from.amountWei, symbol: action.from.symbol }];

    const approveIface = new ethers.Interface(ERC20_ABI);

    for (const item of approvals) {
      if (isNative(item.address)) continue;
      rememberToken(item);
      const token = new ethers.Contract(item.address, ERC20_ABI, signer);
      const amountWei = BigInt(item.amountWei);
      const allowance = await token.allowance(from, spender);
      if (allowance < amountWei) {
        append("assistant", `Approve ${item.symbol || "token"} in your wallet.`);
        const approveData = approveIface.encodeFunctionData("approve", [spender, amountWei]);
        const approveTx = await signer.sendTransaction({
          to: item.address,
          data: approveData,
        });
        await approveTx.wait();
      }
    }

    let data = action.tx.data;
    if (isGift && action.memo) {
      const giftIface = new ethers.Interface([
        "function transferWithMemo(address to, uint256 amount, bytes32 memo) returns (bool)",
      ]);
      const memoBytes = ethers.encodeBytes32String(String(action.memo).slice(0, 31));
      data = giftIface.encodeFunctionData("transferWithMemo", [
        action.to.address,
        action.from.amountWei,
        memoBytes,
      ]);
    } else if (isGift) {
      const giftIface = new ethers.Interface([
        "function transfer(address to, uint256 amount) returns (bool)",
      ]);
      data = giftIface.encodeFunctionData("transfer", [
        action.to.address,
        action.from.amountWei,
      ]);
    }
    if (action.kind === "slip_lp_add") {
      const raw = action.raw || {};
      const a = action.from || {};
      const b = action.to || {};
      const addrA = (raw.token0 || a.address || "").toLowerCase();
      const addrB = (raw.token1 || b.address || "").toLowerCase();
      const token0 = addrA < addrB ? (raw.token0 || a.address) : (raw.token1 || b.address);
      const token1 = addrA < addrB ? (raw.token1 || b.address) : (raw.token0 || a.address);
      const amount0Desired = raw.amount0Desired || (addrA < addrB ? a.amountWei : b.amountWei);
      const amount1Desired = raw.amount1Desired || (addrA < addrB ? b.amountWei : a.amountWei);
      const iface = new ethers.Interface([
        "function mint((address token0, address token1, int24 tickSpacing, int24 tickLower, int24 tickUpper, uint256 amount0Desired, uint256 amount1Desired, uint256 amount0Min, uint256 amount1Min, address recipient, uint256 deadline, uint160 sqrtPriceX96)) payable returns (uint256, uint128, uint256, uint256)",
      ]);
      data = iface.encodeFunctionData("mint", [{
        token0,
        token1,
        tickSpacing: raw.tickSpacing ?? 50,
        tickLower: raw.tickLower ?? -887250,
        tickUpper: raw.tickUpper ?? 887250,
        amount0Desired,
        amount1Desired,
        amount0Min: 0,
        amount1Min: 0,
        recipient: from,
        deadline: Math.floor(Date.now() / 1000) + 1200,
        sqrtPriceX96: 0,
      }]);
      console.log("lp mint ethers", { to: action.tx.to, data, raw });
    } else if (action.kind === "uni_lp_add") {
      const raw = action.raw || {};
      const a = action.from || {};
      const b = action.to || {};
      const addrA = (raw.token0 || a.address || "").toLowerCase();
      const addrB = (raw.token1 || b.address || "").toLowerCase();
      const token0 = addrA < addrB ? (raw.token0 || a.address) : (raw.token1 || b.address);
      const token1 = addrA < addrB ? (raw.token1 || b.address) : (raw.token0 || a.address);
      const amount0Desired = raw.amount0Desired || (addrA < addrB ? a.amountWei : b.amountWei);
      const amount1Desired = raw.amount1Desired || (addrA < addrB ? b.amountWei : a.amountWei);
      const fee = Number(raw.fee || 3000);
      const spacing = fee === 500 ? 10 : fee === 10000 ? 200 : 60;
      const tickLower = raw.tickLower ?? Math.floor(-887220 / spacing) * spacing;
      const tickUpper = raw.tickUpper ?? Math.floor(887220 / spacing) * spacing;
      const iface = new ethers.Interface([
        "function mint((address token0, address token1, uint24 fee, int24 tickLower, int24 tickUpper, uint256 amount0Desired, uint256 amount1Desired, uint256 amount0Min, uint256 amount1Min, address recipient, uint256 deadline)) payable returns (uint256, uint128, uint256, uint256)",
      ]);
      data = iface.encodeFunctionData("mint", [{
        token0,
        token1,
        fee,
        tickLower,
        tickUpper,
        amount0Desired,
        amount1Desired,
        amount0Min: 0,
        amount1Min: 0,
        recipient: from,
        deadline: Math.floor(Date.now() / 1000) + 1200,
      }]);
      console.log("uni mint ethers", { to: action.tx.to, fee, tickLower, tickUpper, data });
    }
    
    if (action.kind === "uni_lp_remove" || action.kind === "slip_lp_remove") {
      const id = BigInt(action.raw?.tokenId || 0);
      const liq = BigInt(action.from?.amountWei || action.raw?.liquidity || 0);
      const npmAddr = action.tx.to;
      const nft = new ethers.Contract(npmAddr, [
        "function ownerOf(uint256 tokenId) view returns (address)",
      ], signer);
      const owner = await nft.ownerOf(id);
      console.log("lp remove", { id: id.toString(), owner, from, npmAddr, liq: liq.toString() });
      if (owner.toLowerCase() !== from.toLowerCase()) {
        throw new Error(`This wallet does not own NFT #${id}. Owner is ${owner}.`);
      }
    }

    if (action.kind === "uni_lp_remove") {
      const id = BigInt(action.raw.tokenId);
      const liq = BigInt(action.from.amountWei);
      const npm = new ethers.Interface([
        "function decreaseLiquidity((uint256 tokenId, uint128 liquidity, uint256 amount0Min, uint256 amount1Min, uint256 deadline)) payable returns (uint256, uint256)",
        "function collect((uint256 tokenId, address recipient, uint128 amount0Max, uint128 amount1Max)) payable returns (uint256, uint256)",
        "function burn(uint256 tokenId)",
        "function multicall(bytes[] data) payable returns (bytes[])",
      ]);
      const deadline = Math.floor(Date.now() / 1000) + 1200;
      const maxU128 = (1n << 128n) - 1n;
      const calls = [
        npm.encodeFunctionData("decreaseLiquidity", [{
          tokenId: id, liquidity: liq, amount0Min: 0, amount1Min: 0, deadline,
        }]),
        npm.encodeFunctionData("collect", [{
          tokenId: id, recipient: from, amount0Max: maxU128, amount1Max: maxU128,
        }]),
      ];
      if (Number(action.raw?.fraction ?? 1) >= 1) {
        calls.push(npm.encodeFunctionData("burn", [id]));
      }
      data = npm.encodeFunctionData("multicall", [calls]);
    }

    const kind = `${action.kind || ""} ${action.protocol || ""} ${action.route || ""}`;
    const skipSuffix = /lp_add|lp_remove|slip|uni_lp|mint/i.test(kind) || (isGift && Boolean(action.memo));
    const tx = await signer.sendTransaction({
      to: action.tx.to,
      data: skipSuffix ? data : withBuilderSuffix(data),
      value: action.tx.value && action.tx.value !== "0" ? action.tx.value : 0,
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
      body: JSON.stringify({
        wallet,
        tx_hash: hash,
        explorer: action.explorer || "",
        kind: action.kind || action.type,
        route: action.protocol || action.route || "",
        from_symbol: action.from?.symbol || "",
        to_symbol: action.to?.symbol || "",
        from_amount: action.from?.amount || "",
        to_amount: action.to?.amount || "",
      }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || "Could not record trade.");
    const link = document.createElement("div");
    link.className = "msg assistant";
    link.innerHTML = "Trade recorded. ";
    const explorerLink = document.createElement("a");
    explorerLink.href = body.explorer || `https://basescan.org/tx/${hash}`;
    explorerLink.target = "_blank";
    explorerLink.rel = "noopener";
    explorerLink.textContent = "View on Basescan";
    link.append(explorerLink);
    appendHtml(link);
    await loadTradeHistory(wallet);
  }

  async function sendChat(text) {
    if (!signedIn) {
      append("user", text);
      append("assistant", "Sign the login message in your wallet to use Stocktalk.");
      pendingConnectPrompt = text;
      await connectWallet({ request: true, replay: true });
      return;
    }

    append("user", text);
    if (sendBtn) sendBtn.disabled = true;
    const status = append("assistant", "Thinking…", "thinking");
    let slow;
    let gathering;
    let finalizing;
    try {
      if (!tokens.length) await loadTokens();
      const balances = wallet ? await readBalances() : [];
      const request = fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          wallet,
          thread_id: sessionThread(),
          balances,
        }),
      });
      slow = setTimeout(() => {
        if (status.isConnected) status.textContent = "Still thinking…";
      }, 5000);
      gathering = setTimeout(() => {
        if (status.isConnected) status.textContent = "Gathering resources…";
      }, 15000);
      finalizing = setTimeout(() => {
        if (status.isConnected) status.textContent = "Finalizing…";
      }, 25000);
      const res = await request;
      const data = await res.json();
      if (res.status === 401) {
        signedIn = false;
        paintWalletButton();
        status.textContent = data.error || "Sign in with your wallet first.";
        status.classList.add("error");
        return;
      }
      if (!res.ok) {
        status.textContent = data.error || "Chat failed";
        status.classList.add("error");
        return;
      }
      status.innerHTML = renderMarkdown(data.message || "");
      status.classList.remove("thinking");
      logEl.scrollTop = logEl.scrollHeight;
      if (!data.message) status.remove();

      const said = String(data.message || "");
      const wantsWallet = /connect (a )?(base )?wallet/i.test(said);
      if (wantsWallet && !pendingConnectPrompt) {
        pendingConnectPrompt = text;
      }
      if (wallet && signedIn && !wantsWallet) {
        pendingConnectPrompt = null;
      }

      if (data.action?.type === "gift_form") {
        renderGiftCard(data.action);
      } else if (data.action?.type === "quote" || data.action?.type === "tx" || data.action?.type === "gift") {
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
      clearTimeout(gathering);
      clearTimeout(finalizing);
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

  historyToggle?.addEventListener("click", () => {
    if (historyMobilePanel?.classList.contains("is-open")) closeHistory();
    else openHistory();
  });
  historyClose?.addEventListener("click", closeHistory);
  historyBackdrop?.addEventListener("click", closeHistory);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeHistory();
  });

  const promptButtons = document.querySelectorAll(".empty-chip");
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
    renderHistory();
    paintWalletButton();
    await loadTokens().catch(() => {});
    if (getInjectedProvider()) {
      try {
        await connectWallet({ request: false, replay: false });
      } catch (_err) {
        persistWallet(null);
      }
    }
    const pending = sessionStorage.getItem("stocktalk.pending_prompt");
    if (pending) {
      sessionStorage.removeItem("stocktalk.pending_prompt");
      if (signedIn) {
        await sendChat(landingPromptText(pending));
      } else {
        pendingConnectPrompt = landingPromptText(pending);
      }
    }
  })();
}