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
    const promptMap = {
      "swap $2 USD for AAPL": "swap $2 USDT for TSLA",
      "check my portfolio balances on Base": "check my portfolio balances",
      "swap 1 TSLA for USDC": "swap 10% of my TSLA for WETH",
    };
    return promptMap[prompt] || prompt;
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
    const connected = Boolean(wallet);
    if (historyToggle) historyToggle.hidden = !connected;
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
    if (!wallet) return;
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
    if (!wallet) {
      walletBtn.classList.remove("connected");
      walletBtn.innerHTML = "Connect wallet";
      if (disconnectBtn) disconnectBtn.hidden = true;
      if (walletCopyPopup) walletCopyPopup.hidden = true;
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
    wallet = addr ? addr.toLowerCase() : null;
    walletProfile = { name: null, avatar: null };
    if (persist) persistWallet(wallet);
    paintWalletButton();
    if (wallet) {
      resolveIdentity(wallet);
      await loadTradeHistory(wallet);
    } else {
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

  async function connectWallet({ request = true } = {}) {
    const eth = getInjectedProvider();
    if (!eth) {
      append("assistant", "No injected wallet. Install MetaMask and refresh.", "error");
      return;
    }
    window.ethereum = eth;
    await ensureBase();
    const method = request ? "eth_requestAccounts" : "eth_accounts";
    const accounts = await eth.request({ method });
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
  }

  walletBtn.addEventListener("click", () => {
    if (wallet) {
      if (walletCopyPopup) walletCopyPopup.hidden = !walletCopyPopup.hidden;
      return;
    }
    connectWallet({ request: true }).catch((err) =>
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

  disconnectBtn?.addEventListener("click", () => {
    disconnectWallet();
    append("assistant", "Wallet disconnected.");
  });

  const liveEth = getInjectedProvider();
  if (liveEth) {
    liveEth.on?.("accountsChanged", (accounts) => {
      const next = accounts?.[0] || null;
      if (next) setWallet(next);
      else disconnectWallet();
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

  async function executeQuote(action, confirmBtn, cancelBtn) {
    const eth = getInjectedProvider();
    if (!eth) throw new Error("Connect a wallet first.");
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;

    await ensureBase();
    if (!wallet) await connectWallet({ request: true });

    const provider = new ethers.BrowserProvider(eth);
    const signer = await provider.getSigner();
    const from = await signer.getAddress();
    await setWallet(from);

    const spender = action.spender;
    if (!spender) throw new Error("Quote is missing a spender.");
    if (!action.tx?.to || !action.tx?.data) throw new Error("Quote is missing transaction data.");

    const sellingNative = isNative(action.from?.address);
    const skipApprove = sellingNative || [
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
          data: withBuilderSuffix(approveData),
        });
        await approveTx.wait();
      }
    }

    const tx = await signer.sendTransaction({
      to: action.tx.to,
      data: withBuilderSuffix(action.tx.data),
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
      if (!res.ok) {
        status.textContent = data.error || "Chat failed";
        status.classList.add("error");
        return;
      }
      status.innerHTML = renderMarkdown(data.message || "");
      status.classList.remove("thinking");
      logEl.scrollTop = logEl.scrollHeight;
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
    renderHistory();
    paintWalletButton();
    await loadTokens().catch(() => {});
    if (localStorage.getItem(WALLET_KEY) && getInjectedProvider()) {
      try {
        await connectWallet({ request: false });
      } catch (_err) {
        persistWallet(null);
      }
    }
    const pending = sessionStorage.getItem("stocktalk.pending_prompt");
    if (pending) {
      sessionStorage.removeItem("stocktalk.pending_prompt");
      await sendChat(landingPromptText(pending));
    }
  })();
}