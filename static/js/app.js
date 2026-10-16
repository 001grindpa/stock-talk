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
  const WALLET_PROVIDER_KEY = "stocktalk.walletProvider";
  const BALANCES_CACHE_KEY = "stocktalk.balances";
  const BASE_L2_RESOLVER = "0xC6d566A56A1aFf6508b41f6c90ff131615583BCD";
  const BASE_RPC_URL = window.STOCKTALK?.baseRpcUrl || "https://mainnet.base.org";
  const baseJsonProvider = new ethers.JsonRpcProvider(
    BASE_RPC_URL,
    { chainId: BASE_CHAIN_ID, name: "base" },
    { staticNetwork: true }
  );
  const MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11";
  const MULTICALL3_ABI = [
    "function aggregate3(tuple(address target, bool allowFailure, bytes callData)[] calls) view returns (tuple(bool success, bytes returnData)[])",
    "function getEthBalance(address addr) view returns (uint256 balance)",
  ];
  const multicallInterface = new ethers.Interface(MULTICALL3_ABI);
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

  function humanTxError(err) {
    const raw = [
      err?.shortMessage,
      err?.reason,
      err?.info?.error?.message,
      err?.message,
      String(err || ""),
    ].join(" ");
    if (/TRANSFER_FROM_FAILED|transfer amount exceeds balance|insufficient/i.test(raw)) {
      return "Not enough token balance or allowance for this swap. The first swap may have used the USDC this basket still needed.";
    }
    if (/user rejected|denied|rejected the request/i.test(raw)) {
      return "You rejected the wallet prompt.";
    }
    if (/TRANSFER_FROM_FAILED|allowance/i.test(raw)) {
      return "Token approval is missing or too small for this swap.";
    }
    return err?.shortMessage || err?.reason || err?.message || "Transaction failed.";
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
  const erc20Interface = new ethers.Interface(ERC20_ABI);

  function getReadProvider() {
    const eth = getInjectedProvider();
    if (eth && window.ethereum) {
      try {
        return new ethers.BrowserProvider(eth);
      } catch (_err) {}
    }
    return baseJsonProvider;
  }

  const logEl = document.getElementById("log");
  const form = document.getElementById("composer");
  const input = document.getElementById("prompt");
  const sendBtn = document.getElementById("send-btn");
  const walletBtn = document.getElementById("wallet-btn");
  const walletChoicePopup = document.getElementById("wallet-choice-popup");
  const connectCoinbaseWallet = document.getElementById("connect-coinbase-wallet");
  const connectOtherWallet = document.getElementById("connect-other-wallet");
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
  const balancesPanel = document.getElementById("sidebar-balances");
  const disconnectBtn = document.getElementById("disconnect-btn");
  const balancesToggle = document.getElementById("balances-toggle");
  const balancesBackdrop = document.getElementById("balances-backdrop");

  let wallet = localStorage.getItem(WALLET_KEY) || null;
  let signedIn = false;
  let isConnecting = false;
  let selectedProviderType = localStorage.getItem(WALLET_PROVIDER_KEY) || null;
  let connectingAddress = null;
  let pendingConnectPrompt = null;
  let walletProfile = { name: null, avatar: null };
  let tokens = [];
  let tokenLoad = null;
  let lastBalances = [];
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

  function openBalances() {
    balancesPanel?.classList.add("is-open");
    balancesBackdrop?.classList.add("is-visible");
    balancesPanel?.setAttribute("aria-hidden", "false");
    balancesBackdrop?.setAttribute("aria-hidden", "false");
    balancesToggle?.setAttribute("aria-expanded", "true");
    balancesToggle?.setAttribute("aria-label", "Close balances");
  }

  function closeBalances() {
    balancesPanel?.classList.remove("is-open");
    balancesBackdrop?.classList.remove("is-visible");
    balancesPanel?.setAttribute("aria-hidden", "true");
    balancesBackdrop?.setAttribute("aria-hidden", "true");
    balancesToggle?.setAttribute("aria-expanded", "false");
    balancesToggle?.setAttribute("aria-label", "Open balances");
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
    if (addr) {
      localStorage.setItem(WALLET_KEY, addr.toLowerCase());
    } else {
      localStorage.removeItem(WALLET_KEY);
      localStorage.removeItem(WALLET_PROVIDER_KEY);
      selectedProviderType = null;
    }
  }

  function getInjectedProvider(type = selectedProviderType) {
    const list = [];
    if (Array.isArray(window.ethereum?.providers)) list.push(...window.ethereum.providers);
    if (window.ethereum) list.push(window.ethereum);
    if (window.okxwallet) list.push(window.okxwallet);
    if (window.coinbaseWalletExtension) list.push(window.coinbaseWalletExtension);
    const providers = [...new Set(list)].filter((provider) => typeof provider?.request === "function");
    if (type === "coinbase") {
      return providers.find((provider) => provider?.isCoinbaseWallet || provider?.isCoinbaseBrowser) || null;
    }
    if (type === "other") {
      return (
        providers.find((provider) => provider?.isMetaMask && !provider?.isBraveWallet) ||
        providers.find((provider) => provider?.isOkxWallet || provider?.isOKXWallet || provider?.isOKExWallet) ||
        providers.find((provider) => !provider?.isCoinbaseWallet && !provider?.isCoinbaseBrowser) ||
        null
      );
    }
    return (
      providers.find((p) => p?.isMetaMask && !p?.isBraveWallet) ||
      providers.find((p) => p?.isCoinbaseWallet || p?.isCoinbaseBrowser) ||
      providers.find((p) => p?.isRabby) ||
      providers[0] ||
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
      walletBtn.setAttribute("aria-expanded", "false");
      if (disconnectBtn) disconnectBtn.hidden = true;
      if (walletCopyPopup) walletCopyPopup.hidden = true;
      return;
    }
    walletBtn.classList.add("connected");
    const name = walletProfile.name || "";
    const label = name
      ? (name.length > 20 ? `${name.slice(0, 10)}…${name.slice(-7)}` : name)
      : shortAddr(wallet);
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
          } catch (_err) { }
        }

        identityCache.set(addr, { ...walletProfile });
        paintWalletButton();
        return;
      }
    } catch (_err) { }

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
    } catch (_err) { }

    identityCache.set(addr, { ...walletProfile });
    paintWalletButton();
  }

  async function setWallet(addr, { persist = true } = {}) {
    const nextWallet = addr ? addr.toLowerCase() : null;
    if (wallet !== nextWallet) lastBalances = [];
    wallet = nextWallet;
    walletProfile = { name: null, avatar: null };
    if (persist) persistWallet(wallet);
    paintWalletButton();
    if (wallet) {
      resolveIdentity(wallet);
      loadTradeHistory(wallet);
    } else {
      tradeHistory = [];
      renderHistory();
    }
    renderBalancesPanel();
  }

  function getBalancesCache(addr) {
    try {
      const cached = JSON.parse(localStorage.getItem(`${BALANCES_CACHE_KEY}.${addr}`) || "null");
      return Array.isArray(cached?.walletBalances) && typeof cached.positions === "string"
        ? cached
        : null;
    } catch (_err) {
      return null;
    }
  }

  function saveBalancesCache(addr, walletBalances, positions) {
    try {
      localStorage.setItem(
        `${BALANCES_CACHE_KEY}.${addr}`,
        JSON.stringify({ walletBalances, positions })
      );
    } catch (_err) {}
  }

  const withdrawablePositionsCache = new Map();

  function getCachedTokenBalance(tokenOrSymbol) {
    if (!tokenOrSymbol) return null;
    let symbol = (typeof tokenOrSymbol === "object" ? tokenOrSymbol.symbol : tokenOrSymbol || "").toUpperCase();
    let address = (typeof tokenOrSymbol === "object" ? tokenOrSymbol.address : "")?.toLowerCase();
    let decimals = Number(typeof tokenOrSymbol === "object" ? tokenOrSymbol.decimals ?? 18 : 18);

    if (!address && symbol && Array.isArray(tokens)) {
      const found = tokens.find((t) => (t.symbol || "").toUpperCase() === symbol);
      if (found) {
        address = (found.address || "").toLowerCase();
        decimals = Number(found.decimals ?? decimals);
      }
    }

    const isNativeToken = symbol === "ETH" || (address && isNative(address));

    const matches = (item) => {
      if (!item) return false;
      const itemSym = String(item.symbol || "").toUpperCase();
      const itemAddr = String(item.address || "").toLowerCase();
      if (isNativeToken && (itemSym === "ETH" || isNative(itemAddr))) {
        return true;
      }
      if (address && itemAddr && itemAddr === address) {
        return true;
      }
      if (symbol && itemSym && itemSym === symbol) {
        return true;
      }
      if (symbol && itemSym) {
        const cleanSymbol = symbol.replace(/C$/, "");
        const cleanItemSym = itemSym.replace(/C$/, "");
        if (cleanSymbol && cleanSymbol === cleanItemSym && cleanSymbol !== "USD") {
          return true;
        }
      }
      return false;
    };

    const formatResult = (item) => {
      const dec = Number(item.decimals ?? decimals);
      const raw = String(item.raw ?? "0");
      let formatted = item.formatted;
      if (formatted === undefined || formatted === null) {
        try {
          formatted = ethers.formatUnits(BigInt(raw), dec);
        } catch (_) {
          formatted = "0";
        }
      }
      return {
        symbol: symbol || item.symbol,
        name: item.name || item.symbol || symbol,
        address: address || item.address,
        decimals: dec,
        raw,
        formatted: String(formatted),
      };
    };

    if (Array.isArray(lastBalances) && lastBalances.length) {
      const found = lastBalances.find(matches);
      if (found) return formatResult(found);
    }

    if (wallet) {
      const cached = getBalancesCache(wallet);
      if (Array.isArray(cached?.walletBalances)) {
        const found = cached.walletBalances.find(matches);
        if (found) return formatResult(found);
      }
    }

    return {
      symbol,
      address,
      decimals,
      raw: "0",
      formatted: "0",
    };
  }

  async function compareCachedBalances(addr) {
    const cached = getBalancesCache(addr);
    if (!cached?.walletBalances?.length && typeof cached?.positions !== "string") return;

    const socketProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${socketProtocol}//${window.location.host}/ws/balances`);
    const result = await new Promise((resolve, reject) => {
      let settled = false;
      const finish = (callback, value) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeout);
        socket.close();
        callback(value);
      };
      const timeout = window.setTimeout(
        () => finish(reject, new Error("Balance comparison timed out.")),
        20000
      );

      socket.addEventListener("open", () => {
        const payload = { wallet: addr };
        if (Array.isArray(cached.walletBalances) && cached.walletBalances.length) {
          payload.balances = cached.walletBalances.map(({ address, raw }) => ({ address, raw }));
        }
        if (typeof cached.positions === "string") {
          payload.positions = cached.positions;
        }
        socket.send(JSON.stringify(payload));
      }, { once: true });
      socket.addEventListener("message", (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "error") {
            throw new Error(message.error || "Could not verify current wallet balances.");
          }
          if (message.type !== "result" || typeof message.unchanged !== "boolean") {
            throw new Error("Invalid balance comparison response.");
          }
          finish(resolve, message);
        } catch (error) {
          finish(reject, error);
        }
      }, { once: true });
      socket.addEventListener("error", () => {
        finish(reject, new Error("Balance comparison connection failed."));
      }, { once: true });
      socket.addEventListener("close", () => {
        if (!settled) finish(reject, new Error("Balance comparison connection closed."));
      }, { once: true });
    });

    if (result.unchanged || wallet !== addr || !signedIn) return;
    let updatedBalances = cached.walletBalances || [];
    if (result.balances && Array.isArray(cached.walletBalances)) {
      updatedBalances = cached.walletBalances.map((item) => {
        const raw = result.balances?.[item.address.toLowerCase()];
        if (raw === undefined || !/^(0|[1-9][0-9]*)$/.test(raw || "")) {
          return item;
        }
        const decimals = Number(item.decimals ?? 18);
        return {
          ...item,
          raw,
          formatted: ethers.formatUnits(BigInt(raw), decimals),
        };
      });
      lastBalances = updatedBalances;
    }
    const updatedPositions = typeof result.positions === "string"
      ? result.positions
      : cached.positions;
    saveBalancesCache(addr, updatedBalances, updatedPositions);
    void renderBalancesPanel();
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
    if (!tokenLoad) {
      tokenLoad = (async () => {
        const res = await fetch("/api/tokens");
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Could not load tokens.");
        tokens = data.tokens || [];
      })().finally(() => {
        tokenLoad = null;
      });
    }
    return tokenLoad;
  }

  function detectActionChanges(action) {
    if (!action) {
      return { wallet: true, defi: true, lp: true };
    }
    const kind = String(action.kind || "").toLowerCase();
    const type = String(action.type || "").toLowerCase();
    const protocol = String(action.protocol || "").toLowerCase();

    const isLp =
      kind.includes("_lp_") ||
      kind.startsWith("lp_") ||
      kind.endsWith("_lp") ||
      kind.startsWith("slip_lp") ||
      kind.startsWith("uni_lp") ||
      ["lp_add", "lp_remove", "slip_lp_add", "slip_lp_remove", "uni_lp_add", "uni_lp_remove"].includes(kind) ||
      (["aerodrome", "slipstream", "uniswap"].includes(protocol) && (kind.includes("lp") || kind.includes("mint") || kind.includes("decrease")));

    if (isLp) {
      return { wallet: true, lp: true, defi: false };
    }

    const isDefi =
      kind.startsWith("aave_") ||
      kind.startsWith("morpho_") ||
      ["aave", "aave_v4", "morpho"].includes(protocol);

    if (isDefi) {
      const isPureCollateral =
        kind.includes("_collateral") ||
        kind.endsWith("_collateral");
      return { wallet: !isPureCollateral, defi: true, lp: false };
    }

    const isSwapOrToken =
      type === "quote" ||
      type === "swap" ||
      type === "gift" ||
      kind === "swap" ||
      kind === "gift_transfer" ||
      kind === "transfer";

    if (isSwapOrToken) {
      return { wallet: true, defi: false, lp: false };
    }

    return { wallet: true, defi: true, lp: true };
  }

  function extractDefiBlocks(positionsText) {
    if (!positionsText) return "";
    return positionsText
      .split(/\n\s*\n/)
      .map((b) => b.trim())
      .filter((b) => b.startsWith("Aave V3") || b.startsWith("Aave V4") || b.startsWith("Morpho"))
      .join("\n\n");
  }

  function extractLpBlocks(positionsText) {
    if (!positionsText) return "";
    return positionsText
      .split(/\n\s*\n/)
      .map((b) => b.trim())
      .filter((b) => b.startsWith("LP positions:") || b.startsWith("LP"))
      .join("\n\n");
  }

  function combinePositionBlocks(defiText, lpText) {
    const parts = [];
    if (defiText && defiText.trim()) parts.push(defiText.trim());
    if (lpText && lpText.trim()) parts.push(lpText.trim());
    return parts.join("\n\n");
  }

  function parseDefiRows(positionsDescription) {
    const defiRows = [];
    if (!positionsDescription) return defiRows;
    const blocks = positionsDescription.split(/\n\s*\n/);
    for (const rawBlock of blocks) {
      const block = rawBlock.trim();
      if (block.startsWith("Aave V3")) {
        for (const [label, match] of [
          ["collateral", block.match(/^Collateral: \$([\d,.]+)/m)],
          ["debt", block.match(/^Debt: \$([\d,.]+)/m)],
        ]) {
          const amount = Number((match?.[1] || "0").replace(/,/g, ""));
          if (amount > 0) {
            defiRows.push(`Aave V3 · $${amount.toLocaleString(undefined, { maximumSignificantDigits: 8 })} ${label}`);
          }
        }
      } else if (block.startsWith("Aave V4")) {
        for (const line of block.split("\n")) {
          const match = line.match(/^(supplied|borrowed) ([^:]+): ([\d.]+)/i);
          if (match && Number(match[3]) > 0) {
            defiRows.push(`Aave V4 · ${match[3]} ${match[2]} ${match[1]}`);
          }
        }
      } else if (block.startsWith("Morpho")) {
        for (const line of block.split("\n")) {
          const match = line.match(/^(.+): collateral ([\d.]+) ([^,]+), borrowShares (\d+).*supplyShares (\d+)/);
          if (!match) continue;
          const collateral = Number(match[2]);
          const hasShares = Number(match[4]) > 0 || Number(match[5]) > 0;
          if (collateral > 0) {
            defiRows.push(`Morpho · ${match[2]} ${match[3]} collateral`);
          } else if (hasShares) {
            defiRows.push(`Morpho · ${match[1]} position`);
          }
        }
      }
    }
    return defiRows;
  }

  function parseLpRows(positionsDescription) {
    const lpRows = [];
    if (!positionsDescription) return lpRows;
    const blocks = positionsDescription.split(/\n\s*\n/);
    for (const rawBlock of blocks) {
      const block = rawBlock.trim();
      if (block.startsWith("LP positions:") || block.startsWith("LP")) {
        for (const line of block.split("\n")) {
          const trimmed = line.trim();
          if (
            !trimmed ||
            trimmed.startsWith("LP positions") ||
            trimmed.toLowerCase().includes("no lp positions") ||
            trimmed.toLowerCase() === "none" ||
            trimmed.toLowerCase().includes("no aerodrome, slipstream, or uniswap")
          ) {
            continue;
          }
          lpRows.push(trimmed);
        }
      }
    }
    return lpRows;
  }

  function buildWalletRows(balancesList, tokensList) {
    const rows = [];
    const balancesByAddress = new Map(
      (balancesList || []).map((item) => [item.address?.toLowerCase(), item])
    );
    const balancesBySymbol = new Map(
      (balancesList || []).map((item) => [item.symbol?.toUpperCase(), item])
    );
    const seenAddresses = new Set();

    for (const token of (tokensList || [])) {
      if (!token?.address) continue;
      const addr = token.address.toLowerCase();
      seenAddresses.add(addr);

      if (isNative(token.address) || token.symbol?.toUpperCase() === "ETH") {
        const ethBal = balancesByAddress.get(NATIVE_ETH.toLowerCase()) ||
          balancesByAddress.get(token.address.toLowerCase()) ||
          balancesBySymbol.get("ETH");
        rows.push({
          symbol: "ETH",
          address: token.address,
          formatted: ethBal?.formatted || "0",
          raw: ethBal?.raw || "0",
        });
      } else {
        const balance = balancesByAddress.get(addr) || balancesBySymbol.get(token.symbol?.toUpperCase());
        rows.push({
          ...token,
          formatted: balance ? balance.formatted : "0",
          raw: balance ? balance.raw : "0",
        });
      }
    }

    for (const item of (balancesList || [])) {
      if (!item?.address) continue;
      const addr = item.address.toLowerCase();
      if (seenAddresses.has(addr) || isNative(item.address) || item.symbol?.toUpperCase() === "ETH") continue;
      seenAddresses.add(addr);
      rows.push({
        symbol: item.symbol,
        address: item.address,
        formatted: item.formatted || "0",
        raw: item.raw || "0",
      });
    }
    return rows;
  }

  const formatBalance = (value) => {
    const amount = Number(value || 0);
    return Number.isFinite(amount)
      ? amount.toLocaleString(undefined, { maximumSignificantDigits: 8 })
      : "0";
  };

  function renderWalletGroupContent(walletRows, walletError) {
    if (walletError) return '<div class="balances-status">Balances unavailable</div>';
    return (
      (walletRows || [])
        .filter((item) => Number(item.formatted) > 0 || ["USDC", "ETH"].includes(item.symbol?.toUpperCase()))
        .map((item) => `<div class="balances-row"><span>${esc(item.symbol)}</span><strong>${esc(formatBalance(item.formatted))}</strong></div>`)
        .join("") || '<div class="balances-status">No token balances</div>'
    );
  }

  function renderDefiGroupContent(defiRows, defiError) {
    if (defiError) return '<div class="balances-status">Balances unavailable</div>';
    return defiRows && defiRows.length
      ? defiRows.map((row) => `<div class="balances-row"><span>${esc(row)}</span></div>`).join("")
      : '<div class="balances-status">No DeFi positions</div>';
  }

  function renderLpGroupContent(lpRows, lpError) {
    if (lpError) return '<div class="balances-status">Balances unavailable</div>';
    return lpRows && lpRows.length
      ? lpRows.map((row) => `<div class="balances-row"><span>${esc(row)}</span></div>`).join("")
      : '<div class="balances-status">No LP positions</div>';
  }

  async function renderBalancesPanel({ refresh = false, action = null, target = null } = {}) {
    if (!balancesPanel) return;

    const heading = '<div class="sidebar-header"><h3>Balances</h3></div>';
    if (!wallet || !signedIn) {
      balancesPanel.innerHTML = `${heading}<div class="balances-status">Connect wallet to see balances</div>`;
      return;
    }

    const walletSnapshot = wallet;
    const previousCache = getBalancesCache(walletSnapshot);

    const targets = target
      ? { wallet: Boolean(target.wallet), defi: Boolean(target.defi), lp: Boolean(target.lp) }
      : action
      ? detectActionChanges(action)
      : { wallet: true, defi: true, lp: true };

    const shouldReloadWallet = refresh ? targets.wallet : !previousCache?.walletBalances?.length;
    const shouldReloadDefi = refresh ? targets.defi : typeof previousCache?.positions !== "string";
    const shouldReloadLp = refresh ? targets.lp : typeof previousCache?.positions !== "string";

    if (!lastBalances.length && previousCache?.walletBalances) {
      lastBalances = previousCache.walletBalances;
    }

    let walletGroup = balancesPanel.querySelector(".balances-group-wallet");
    let defiGroup = balancesPanel.querySelector(".balances-group-defi");
    let lpGroup = balancesPanel.querySelector(".balances-group-lp");

    const needsFullSkeleton = !walletGroup || !defiGroup || !lpGroup;
    if (needsFullSkeleton) {
      const initialWalletHtml = previousCache?.walletBalances?.length
        ? renderWalletGroupContent(buildWalletRows(previousCache.walletBalances, tokens), false)
        : '<div class="balances-status">Loading…</div>';
      const initialDefiHtml = typeof previousCache?.positions === "string"
        ? renderDefiGroupContent(parseDefiRows(previousCache.positions), false)
        : '<div class="balances-status">Loading…</div>';
      const initialLpHtml = typeof previousCache?.positions === "string"
        ? renderLpGroupContent(parseLpRows(previousCache.positions), false)
        : '<div class="balances-status">Loading…</div>';

      balancesPanel.innerHTML = `${heading}
        <div class="balances-group balances-group-wallet">
          <h4 class="balances-group-title">Wallet</h4>
          ${initialWalletHtml}
        </div>
        <div class="balances-group balances-group-defi">
          <h4 class="balances-group-title">DeFi</h4>
          ${initialDefiHtml}
        </div>
        <div class="balances-group balances-group-lp">
          <h4 class="balances-group-title">LP</h4>
          ${initialLpHtml}
        </div>`;

      walletGroup = balancesPanel.querySelector(".balances-group-wallet");
      defiGroup = balancesPanel.querySelector(".balances-group-defi");
      lpGroup = balancesPanel.querySelector(".balances-group-lp");
    } else {
      if (shouldReloadWallet) {
        walletGroup.innerHTML = '<h4 class="balances-group-title">Wallet</h4><div class="balances-status">Loading…</div>';
      }
      if (shouldReloadDefi) {
        defiGroup.innerHTML = '<h4 class="balances-group-title">DeFi</h4><div class="balances-status">Loading…</div>';
      }
      if (shouldReloadLp) {
        lpGroup.innerHTML = '<h4 class="balances-group-title">LP</h4><div class="balances-status">Loading…</div>';
      }
    }

    let walletRows = [];
    let walletError = false;
    let defiRows = [];
    let defiError = false;
    let lpRows = [];
    let lpError = false;

    let updatedDefiText = null;
    let updatedLpText = null;

    const tasks = [];

    if (shouldReloadWallet) {
      tasks.push((async () => {
        try {
          if (!tokens.length) await loadTokens();
          lastBalances = await readBalances();
          if (!tokens.length || !lastBalances.length) {
            throw new Error("Wallet balances unavailable");
          }
          walletRows = buildWalletRows(lastBalances, tokens);
        } catch (_err) {
          walletError = true;
        }
      })());
    } else if (previousCache?.walletBalances) {
      walletRows = buildWalletRows(previousCache.walletBalances, tokens);
    }

    if (shouldReloadDefi && shouldReloadLp) {
      tasks.push((async () => {
        try {
          const response = await fetch(`/api/positions?wallet=${encodeURIComponent(walletSnapshot)}`);
          if (!response.ok) throw new Error("Positions request failed");
          const data = await response.json();
          const fullPositions = String(data.positions || "");
          updatedDefiText = extractDefiBlocks(fullPositions);
          updatedLpText = extractLpBlocks(fullPositions);
          defiRows = parseDefiRows(updatedDefiText);
          lpRows = parseLpRows(updatedLpText);
        } catch (_err) {
          defiError = true;
          lpError = true;
        }
      })());
    } else {
      if (shouldReloadDefi) {
        tasks.push((async () => {
          try {
            const response = await fetch(`/api/positions?wallet=${encodeURIComponent(walletSnapshot)}&category=defi`);
            if (!response.ok) throw new Error("DeFi positions request failed");
            const data = await response.json();
            updatedDefiText = String(data.positions || "");
            defiRows = parseDefiRows(updatedDefiText);
          } catch (_err) {
            defiError = true;
          }
        })());
      } else if (typeof previousCache?.positions === "string") {
        defiRows = parseDefiRows(previousCache.positions);
      }

      if (shouldReloadLp) {
        tasks.push((async () => {
          try {
            const response = await fetch(`/api/positions?wallet=${encodeURIComponent(walletSnapshot)}&category=lp`);
            if (!response.ok) throw new Error("LP positions request failed");
            const data = await response.json();
            updatedLpText = String(data.positions || "");
            lpRows = parseLpRows(updatedLpText);
          } catch (_err) {
            lpError = true;
          }
        })());
      } else if (typeof previousCache?.positions === "string") {
        lpRows = parseLpRows(previousCache.positions);
      }
    }

    if (tasks.length > 0) {
      await Promise.all(tasks);
    }

    if (wallet !== walletSnapshot || !signedIn) return;

    if (walletGroup && (shouldReloadWallet || needsFullSkeleton)) {
      walletGroup.innerHTML = `<h4 class="balances-group-title">Wallet</h4>${renderWalletGroupContent(walletRows, walletError)}`;
    }
    if (defiGroup && (shouldReloadDefi || needsFullSkeleton)) {
      defiGroup.innerHTML = `<h4 class="balances-group-title">DeFi</h4>${renderDefiGroupContent(defiRows, defiError)}`;
    }
    if (lpGroup && (shouldReloadLp || needsFullSkeleton)) {
      lpGroup.innerHTML = `<h4 class="balances-group-title">LP</h4>${renderLpGroupContent(lpRows, lpError)}`;
    }

    const currentCachedPositions = previousCache?.positions || "";
    let finalPositions = currentCachedPositions;

    if (updatedDefiText !== null || updatedLpText !== null) {
      const finalDefi = updatedDefiText !== null ? updatedDefiText : extractDefiBlocks(currentCachedPositions);
      const finalLp = updatedLpText !== null ? updatedLpText : extractLpBlocks(currentCachedPositions);
      finalPositions = combinePositionBlocks(finalDefi, finalLp);
    }

    if (!walletError || !defiError || !lpError) {
      saveBalancesCache(walletSnapshot, lastBalances, finalPositions);
    }
  }


  async function readBalances() {
    if (!wallet) return [];
    if (!tokens.length) await loadTokens().catch(() => {});
    const list = [];
    const seen = new Set();
    for (const t of [...tokens, ...extraTokens]) {
      if (!t?.address) continue;
      const key = t.address.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      list.push(t);
    }

    const provider = getReadProvider();
    const out = [];

    // Try Multicall3 first for fast atomic fetching
    try {
      const mcContract = new ethers.Contract(MULTICALL3_ADDRESS, MULTICALL3_ABI, provider);
      const ercTokens = list.filter(
        (t) => !isNative(t.address) && (t.symbol || "").toUpperCase() !== "ETH"
      );

      const calls = [
        {
          target: MULTICALL3_ADDRESS,
          allowFailure: true,
          callData: multicallInterface.encodeFunctionData("getEthBalance", [wallet]),
        },
        ...ercTokens.map((t) => ({
          target: t.address,
          allowFailure: true,
          callData: erc20Interface.encodeFunctionData("balanceOf", [wallet]),
        })),
      ];

      const results = await mcContract.aggregate3(calls);

      const ethRes = results[0];
      if (ethRes && ethRes.success && ethRes.returnData && ethRes.returnData !== "0x") {
        const nativeBal = ethers.toBigInt(ethRes.returnData);
        out.push({
          symbol: "ETH",
          name: "Ether",
          address: "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
          decimals: 18,
          raw: nativeBal.toString(),
          formatted: ethers.formatEther(nativeBal),
        });
      } else {
        out.push({
          symbol: "ETH",
          name: "Ether",
          address: "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
          decimals: 18,
          raw: "0",
          formatted: "0",
        });
      }

      for (let i = 0; i < ercTokens.length; i++) {
        const token = ercTokens[i];
        const res = results[i + 1];
        const decimals = Number(token.decimals ?? 18);
        if (res && res.success && res.returnData && res.returnData !== "0x") {
          try {
            const rawBig = ethers.toBigInt(res.returnData);
            out.push({
              symbol: token.symbol,
              name: token.name || token.symbol,
              address: token.address,
              decimals,
              raw: rawBig.toString(),
              formatted: ethers.formatUnits(rawBig, decimals),
            });
            continue;
          } catch (_err) {}
        }
        out.push({
          symbol: token.symbol,
          name: token.name || token.symbol,
          address: token.address,
          decimals,
          raw: "0",
          formatted: "0",
        });
      }

      lastBalances = out;
      return out;
    } catch (_mcErr) {
      console.warn("Multicall3 balance check failed, falling back to direct calls:", _mcErr);
    }

    try {
      const native = await provider.getBalance(wallet).catch(async () => {
        return baseJsonProvider.getBalance(wallet).catch(() => 0n);
      });
      out.push({
        symbol: "ETH",
        name: "Ether",
        address: "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
        decimals: 18,
        raw: native.toString(),
        formatted: ethers.formatEther(native),
      });
    } catch (_err) {
      out.push({
        symbol: "ETH",
        name: "Ether",
        address: "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
        decimals: 18,
        raw: "0",
        formatted: "0",
      });
    }

    for (const token of list) {
      if (isNative(token.address) || (token.symbol || "").toUpperCase() === "ETH") continue;
      const decimals = Number(token.decimals ?? 18);
      try {
        let contract = new ethers.Contract(token.address, ERC20_ABI, provider);
        let raw;
        try {
          raw = await contract.balanceOf(wallet);
        } catch (_err) {
          contract = new ethers.Contract(token.address, ERC20_ABI, baseJsonProvider);
          raw = await contract.balanceOf(wallet);
        }
        out.push({
          symbol: token.symbol,
          name: token.name || token.symbol,
          address: token.address,
          decimals,
          raw: raw.toString(),
          formatted: ethers.formatUnits(raw, decimals),
        });
      } catch (_err) {
        out.push({
          symbol: token.symbol,
          name: token.name || token.symbol,
          address: token.address,
          decimals,
          raw: "0",
          formatted: "0",
        });
      }
    }

    lastBalances = out;
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

  async function connectWallet({
    request = true,
    replay = false,
    checkCachedBalances = false,
  } = {}) {
    if (isConnecting) return;
    isConnecting = true;
    try {
      const eth = getInjectedProvider();
      if (!eth) {
        if (request) {
          append(
            "assistant",
            "No browser wallet was detected. Install Coinbase Wallet or another EVM-compatible browser wallet, then refresh and try again.",
            "error"
          );
        }
        return;
      }
      window.ethereum = eth;
      if (request) {
        await ensureBase();
      }
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
            if (checkCachedBalances) {
              void compareCachedBalances(normalized).catch((err) => {
                console.warn("Could not compare cached wallet balances:", err);
              });
            }
            if (replay) {
              const retry = pendingConnectPrompt;
              pendingConnectPrompt = null;
              if (retry) sendChat(retry, { skipUser: true });
            }
            return;
          }
        }
      } catch (_err) { }

      if (!request) {
        signedIn = false;
        return;
      }

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

        if (replay) {
          const retry = pendingConnectPrompt;
          pendingConnectPrompt = null;
          if (retry) sendChat(retry, { skipUser: true });
        }
      } catch (err) {
        console.error("Sign-in failed or rejected:", err);
        await setWallet(null);
        signedIn = false;
        await fetch("/api/auth/logout", { method: "POST" }).catch(() => { });
        if (request) append("assistant", "Sign-in cancelled. Connect again and sign the login message.");
      }
    } finally {
      isConnecting = false;
      connectingAddress = null;
    }
  }

  async function disconnectWallet() {
    signedIn = false;
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => { });
    await setWallet(null);
  }

  walletBtn.addEventListener("click", () => {
    if (wallet && signedIn) {
      if (walletCopyPopup) {
        walletCopyPopup.hidden = !walletCopyPopup.hidden;
        walletBtn.setAttribute("aria-expanded", String(!walletCopyPopup.hidden));
      }
      return;
    }
    if (!getInjectedProvider(null)) {
      append(
        "assistant",
        "No browser wallet was detected. Install Coinbase Wallet or another EVM-compatible browser wallet, then refresh and try again.",
        "error"
      );
      return;
    }
    if (walletChoicePopup) {
      walletChoicePopup.hidden = !walletChoicePopup.hidden;
      walletBtn.setAttribute("aria-expanded", String(!walletChoicePopup.hidden));
    }
  });

  async function connectSelectedWallet(type) {
    selectedProviderType = type;
    if (!getInjectedProvider(type)) {
      const message = type === "coinbase"
        ? "Coinbase Wallet wasn't detected. Install Coinbase Wallet, or choose Other browser wallet if you already have another EVM wallet installed."
        : "No other EVM browser wallet was detected. Install MetaMask, OKX Wallet, or another EVM-compatible browser wallet.";
      append("assistant", message, "error");
      return;
    }
    if (walletChoicePopup) walletChoicePopup.hidden = true;
    walletBtn?.setAttribute("aria-expanded", "false");
    try {
      await connectWallet({ request: true, replay: true });
      if (signedIn && wallet) {
        localStorage.setItem(WALLET_PROVIDER_KEY, type);
      }
    } catch (err) {
      append("assistant", err.message || String(err), "error");
    }
  }

  connectCoinbaseWallet?.addEventListener("click", () => connectSelectedWallet("coinbase"));
  connectOtherWallet?.addEventListener("click", () => connectSelectedWallet("other"));

  copyWalletAddress?.addEventListener("click", async () => {
    if (!wallet) return;
    try {
      await navigator.clipboard.writeText(wallet);
      if (walletCopyPopup) walletCopyPopup.hidden = true;
      walletBtn?.setAttribute("aria-expanded", "false");
      copyToast?.classList.add("is-visible");
      clearTimeout(copyToastTimer);
      copyToastTimer = setTimeout(() => copyToast?.classList.remove("is-visible"), 2200);
    } catch (_err) { }
  });

  document.addEventListener("click", (event) => {
    if (
      walletCopyPopup &&
      !walletCopyPopup.hidden &&
      !walletCopyPopup.contains(event.target) &&
      !walletBtn.contains(event.target)
    ) {
      walletCopyPopup.hidden = true;
      walletBtn.setAttribute("aria-expanded", "false");
    }
    if (
      walletChoicePopup &&
      !walletChoicePopup.hidden &&
      !walletChoicePopup.contains(event.target) &&
      !walletBtn.contains(event.target)
    ) {
      walletChoicePopup.hidden = true;
      walletBtn.setAttribute("aria-expanded", "false");
    }
  });

  disconnectBtn?.addEventListener("click", async () => {
    await disconnectWallet();
    walletBtn?.setAttribute("aria-expanded", "false");
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
    liveEth.on?.("chainChanged", (chainId) => {
      const currentChain = String(chainId || "").toLowerCase();
      if (!currentChain) return;
      const previousChain = sessionStorage.getItem("stocktalk.walletChainId");
      sessionStorage.setItem("stocktalk.walletChainId", currentChain);
      if (previousChain && previousChain !== currentChain) {
        window.location.reload();
      }
    });
  }

  function renderEnableCollateralCard(enableAction, symbol) {
    if (!enableAction?.tx?.to) return;
    const card = document.createElement("div");
    card.className = "quote-card";
    const sym = String(symbol || enableAction?.from?.symbol || "Stock").trim();
    card.innerHTML = `
      <h3>${esc(sym)} is supplied, not collateral</h3>
      <p class="muted">Enable it to borrow USDC against it.</p>
      <div class="actions">
        <button type="button" class="primary enable-col">Set as collateral</button>
        <button type="button" class="ghost skip-col">Cancel</button>
      </div>
    `;
    logEl.appendChild(card);
    logEl.scrollTop = logEl.scrollHeight;
    const enableBtn = card.querySelector(".enable-col");
    const skipBtn = card.querySelector(".skip-col");
    
    enableBtn.addEventListener("click", () => {
      enableBtn.disabled = true;
      skipBtn.disabled = true;
      executeQuote(enableAction, enableBtn, skipBtn).catch((err) => {
        append("assistant", humanTxError(err), "error");
        enableBtn.disabled = false;
        skipBtn.disabled = false;
      });
    });
    skipBtn.addEventListener("click", () => {
      enableBtn.disabled = true;
      skipBtn.disabled = true;
      card.remove();
      append("assistant", "Left as supply-only.");
    });
  }

  function playActionEffect(action, card) {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const kind = String(action.kind || "").toLowerCase();
    let effectClass = "";
    if (kind === "aave_v4_collateral") effectClass = "juice-flag";
    else if (kind === "aave_v4_supply") effectClass = "juice-stack";
    else if (kind === "aave_withdraw" || kind === "aave_v4_withdraw") effectClass = "juice-coin";
    else if (kind === "gift_transfer" || action.type === "gift") effectClass = "juice-envelope";
    else if (action.type === "quote" && !/aave|morpho|lp|gift/.test(kind)) effectClass = "juice-coin";
    if (!effectClass) return;

    const effect = document.createElement("span");
    effect.className = `action-juice ${effectClass}`;
    effect.setAttribute("aria-hidden", "true");
    effect.innerHTML = '<span class="juice-sprite"></span>';
    const host = card?.isConnected ? card : logEl;
    host.appendChild(effect);
    window.setTimeout(() => effect.remove(), 1350);
  }

  function editableTokens(action, slot) {
    const kind = action.kind || "";
    const allTokens = (tokens || []).filter((token) => token?.address && token?.symbol);
    const bySymbols = (symbols) =>
      allTokens.filter((token) => symbols.includes((token.symbol || "").toUpperCase()));
    const stocks = allTokens.filter((token) => token.kind === "stock");
    const v4Stocks = stocks.filter((token) =>
      ["AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"].includes(
        (token.symbol || "").toUpperCase().replace(/C$/, "")
      )
    );
    if (action.type === "quote") return allTokens;
    if (slot === "collateral" && kind === "aave_v4_borrow") return v4Stocks;
    if (["lp_add", "lp_remove", "slip_lp_add", "slip_lp_remove", "uni_lp_add", "uni_lp_remove"].includes(kind)) {
      return allTokens.filter((token) => token.kind !== "native");
    }
    if (kind.startsWith("aave_v4_")) {
      return kind === "aave_v4_supply" || kind === "aave_v4_withdraw" || kind === "aave_v4_collateral"
        ? v4Stocks
        : bySymbols(["USDC"]);
    }
    if (kind.startsWith("aave_")) return bySymbols(["USDC", "WETH"]);
    if (kind.startsWith("morpho_")) {
      if (slot === "collateral") {
        return [...stocks, ...bySymbols(["USDC", "WETH"])].filter(
          (token) => ["AAPL", "GOOGL", "NVDA", "META", "SPCX", "USDC", "WETH"].includes(
            (token.symbol || "").toUpperCase().replace(/C$/, "")
          )
        );
      }
      return kind === "morpho_supply" || kind === "morpho_withdraw"
        ? [...stocks, ...bySymbols(["USDC", "WETH"])].filter(
          (token) => ["AAPL", "GOOGL", "NVDA", "META", "SPCX", "USDC", "WETH"].includes(
            (token.symbol || "").toUpperCase().replace(/C$/, "")
          )
        )
        : bySymbols(["USDC", "WETH"]);
    }
    return allTokens;
  }

  function actionTokenSymbol(action, slot) {
    if (action.type === "quote") return action[slot]?.symbol || "";
    const kind = action.kind || "";
    if (slot === "collateral") {
      const label = action.raw?.label || "";
      return action.collateral_symbol || label.split("/")[0] || "";
    }
    if (kind === "aave_v4_borrow") return action.to?.symbol || "USDC";
    if (kind.includes("withdraw")) return action.to?.symbol || action.from?.symbol || "";
    if (kind.includes("_collateral")) return action.from?.symbol || "";
    if (["lp_remove", "slip_lp_remove", "uni_lp_remove"].includes(kind)) {
      const pair = String(action.summary || "").match(/([A-Z0-9]+)\/([A-Z0-9]+)/i);
      if (pair) return pair[slot === "from" ? 1 : 2];
    }
    return action.from?.symbol || action.to?.symbol || "";
  }

  function cardAmount(action) {
    const kind = action.kind || "";
    if (kind.includes("withdraw")) return action.to?.amount || action.from?.amount || "";
    return action.from?.amount || action.to?.amount || "";
  }

  function renderQuoteCard(action) {
    const card = document.createElement("div");
    card.className = "quote-card";
    let currentAction = action;
    const kind = action.kind || "";
    const lpRemove = ["lp_remove", "slip_lp_remove", "uni_lp_remove"].includes(kind);
    const withdrawAction = ["aave_withdraw", "aave_v4_withdraw", "morpho_withdraw"].includes(kind);
    const positionProtocol = lpRemove
      ? kind === "lp_remove" ? "aerodrome" : kind === "slip_lp_remove" ? "slipstream" : "uniswap"
      : kind === "aave_v4_withdraw" ? "aave_v4" : kind === "aave_withdraw" ? "aave" : kind === "morpho_withdraw" ? "morpho" : "";
    const hasPositionSelector = lpRemove || withdrawAction;
    let positionSelectionRequired = Boolean(action.position_selection_required);
    const repayAmountWord = String(action.tx?.data || "").slice(74, 138);
    const fullV4Repay = action.kind === "aave_v4_repay" &&
      /^[\da-f]{64}$/i.test(repayAmountWord) &&
      BigInt(`0x${repayAmountWord}`) === (1n << 256n) - 1n;
    const summaryFraction = Number(String(action.summary || "").match(/(\d+(?:\.\d+)?)%/)?.[1]);
    let fraction = fullV4Repay ? 1 : hasPositionSelector ? (summaryFraction > 0 ? summaryFraction / 100 : 1) : 0;
    let amountEdited = false;
    const mock = Boolean(action.mock) || action.route === "MOCK";
    const canConfirm = !mock || demoEnabled();
    const title = action.type === "tx" ? action.summary || "Confirm on Base" : "Confirm swap on Base";
    const routeLabel = action.protocol || action.route || action.kind || "aerodrome";
    const hasPair = !lpRemove && (action.type === "quote" || (action.kind || "").includes("_lp_") || ["lp_add", "lp_remove"].includes(action.kind));
    const fromOptions = editableTokens(action, "from");
    const toOptions = hasPair ? editableTokens(action, "to") : [];
    const collateralOptions = (
      ["morpho_borrow", "morpho_repay", "aave_v4_borrow"].includes(action.kind)
    )
      ? editableTokens(action, "collateral")
      : [];
    const isCollateralToggle = (action.kind || "").includes("_collateral");
    const defaultToggle = /disable/i.test(action.summary || "") ? "off" : "on";
    const selectMarkup = (className, label, options, selected) => {
      const selectedToken = options.find((token) => String(token.symbol).toUpperCase() === String(selected).toUpperCase());
      const cached = selectedToken ? getCachedTokenBalance(selectedToken) : null;
      const initialBalance = cached && cached.formatted !== undefined && cached.formatted !== null
        ? `Balance: ${cached.formatted} ${selectedToken.symbol}`
        : "Balance: —";
      return `
      <label class="action-editor-field">
        <span>${label}</span>
        <select class="${className}">
          ${options.map((token) => {
            const symbol = String(token.symbol);
            const isSelected = symbol.toUpperCase() === String(selected).toUpperCase();
            return `<option value="${esc(symbol)}" ${isSelected ? "selected" : ""}>${esc(symbol)}</option>`;
          }).join("")}
        </select>
        <small class="action-balance muted">${initialBalance}</small>
      </label>`;
    };
    const positionSelectMarkup = hasPositionSelector ? `
      <label class="action-editor-field">
        <span>Position</span>
        <select class="action-position">
          <option value="">Loading positions…</option>
        </select>
      </label>` : "";
    const amountMarkup = lpRemove
      ? `<output class="action-amount action-amount-display">Loading position…</output>`
      : `<input class="action-amount" type="text" inputmode="decimal" value="${esc(cardAmount(action))}">`;
    card.innerHTML = `
      ${mock ? `<div class="mock-tag">MOCK</div>` : ""}
      <h3 class="action-title">${esc(title)}</h3>
      <div class="quote-row"><span>From</span><strong class="action-from">${esc(action.from ? `${action.from.amount} ${action.from.symbol}` : "—")}</strong></div>
      <div class="quote-row"><span>To</span><strong class="action-to">${esc(action.to ? `${action.to.amount} ${action.to.symbol}` : "—")}</strong></div>
      <div class="quote-row"><span>Route</span><strong class="action-route">${esc(routeLabel)}</strong></div>
      <div class="action-editor">
        ${positionSelectMarkup}
        ${hasPositionSelector ? "" : selectMarkup("action-from-token", hasPair ? "From token / stock" : "Token / stock", fromOptions, actionTokenSymbol(action, "from"))}
        ${hasPositionSelector ? "" : hasPair ? selectMarkup("action-to-token", "To token / stock", toOptions, actionTokenSymbol(action, "to")) : ""}
        ${collateralOptions.length ? selectMarkup("action-collateral-token", "Collateral stock", collateralOptions, actionTokenSymbol(action, "collateral")) : ""}
        ${isCollateralToggle ? `<label class="action-editor-field">
          <span>Collateral setting</span>
          <select class="action-toggle">
            <option value="on" ${defaultToggle === "on" ? "selected" : ""}>Enabled</option>
            <option value="off" ${defaultToggle === "off" ? "selected" : ""}>Disabled</option>
          </select>
        </label>` : `<label class="action-editor-field">
          <span>Amount</span>
          ${amountMarkup}
          ${hasPositionSelector ? `<small class="action-position-balance muted">Position size: loading…</small>` : ""}
          <div class="gift-presets action-presets">
            <button type="button" class="gift-preset" data-frac="0.25">25%</button>
            <button type="button" class="gift-preset" data-frac="0.5">50%</button>
            <button type="button" class="gift-preset" data-frac="0.75">75%</button>
            <button type="button" class="gift-preset" data-frac="1">100%</button>
          </div>
        </label>`}
        <p class="action-edit-error" hidden></p>
        <button type="button" class="action-update">Update transaction</button>
      </div>
      <div class="confirm-actions">
        <button type="button" class="confirm" ${canConfirm && !positionSelectionRequired ? "" : "disabled"}>Confirm in wallet</button>
        <button type="button" class="cancel">Cancel</button>
      </div>
    `;

    const fromEl = card.querySelector(".action-from-token");
    const toEl = card.querySelector(".action-to-token");
    const collateralEl = card.querySelector(".action-collateral-token");
    const toggleEl = card.querySelector(".action-toggle");
    const positionEl = card.querySelector(".action-position");
    const positionBalanceEl = card.querySelector(".action-position-balance");
    const amountEl = card.querySelector(".action-amount");
    const updateBtn = card.querySelector(".action-update");
    const errorEl = card.querySelector(".action-edit-error");
    const confirmBtn = card.querySelector(".confirm");
    const cancelBtn = card.querySelector(".cancel");
    const balanceEls = card.querySelectorAll(".action-balance");
    let needsRebuild = false;
    let canceled = false;
    let swapUpdateTimer = null;
    if (positionSelectionRequired) updateBtn.disabled = true;

    function markDirty() {
      needsRebuild = true;
      confirmBtn.disabled = true;
    }

    function scheduleSwapRebuild() {
      if (action.type !== "quote") return;
      window.clearTimeout(swapUpdateTimer);
      swapUpdateTimer = window.setTimeout(() => {
        swapUpdateTimer = null;
        if (!canceled && needsRebuild) void rebuild();
      }, 180);
    }

    function refreshEditorBalances() {
      const selects = [fromEl, toEl, collateralEl].filter(Boolean);
      for (const [index, select] of selects.entries()) {
        const label = balanceEls[index];
        if (!label || !select) continue;
        const cached = getCachedTokenBalance(select.value);
        if (cached && cached.formatted !== undefined && cached.formatted !== null) {
          label.textContent = `Balance: ${cached.formatted} ${cached.symbol}`;
        } else {
          label.textContent = "Balance: —";
        }
      }
    }

    function selectedPosition() {
      return positionEl?.selectedOptions?.[0] || null;
    }

    function renderPositionBalance() {
      const option = selectedPosition();
      let selectedAmount = "";
      if (option?.dataset.amountRaw && fraction > 0) {
        try {
          const basisPoints = BigInt(Math.round(Math.min(fraction, 1) * 10000));
          const rawAmount = BigInt(option.dataset.amountRaw) * basisPoints / 10000n;
          const decimals = Number(option.dataset.amountDecimals || 0);
          const amount = decimals > 0
            ? ethers.formatUnits(rawAmount, decimals)
            : rawAmount.toLocaleString();
          selectedAmount = `${amount} ${option.dataset.amountSymbol || ""}`.trim();
        } catch (_err) {
          selectedAmount = "";
        }
      }
      if (lpRemove && amountEl) {
        amountEl.textContent = selectedAmount || `${Math.round(fraction * 100)}%`;
      }
      if (positionBalanceEl) {
        positionBalanceEl.textContent = option?.dataset.balance
          ? `Position size: ${option.dataset.balance}${selectedAmount ? ` · ${Math.round(fraction * 100)}% = ${selectedAmount}` : ""}`
          : "Position size: unavailable";
      }
    }

    async function loadPositionOptions() {
      if (!positionEl || !positionProtocol) return;
      const currentId = String(
        currentAction.raw?.pool || currentAction.raw?.tokenId || currentAction.raw?.market || ""
      ).toLowerCase();
      const currentSymbol = String(
        currentAction.to?.symbol || currentAction.from?.symbol || ""
      ).toUpperCase();
      const pairMatch = String(currentAction.summary || "").match(/([A-Z0-9]+)\/([A-Z0-9]+)/i);

      function applyPositions(positions) {
        if (!positions || !positions.length) return false;
        positionSelectionRequired = positionSelectionRequired && positions.length > 1;

        positionEl.replaceChildren();
        positions.forEach((position) => {
          const option = document.createElement("option");
          option.value = String(position.id);
          option.textContent = position.label;
          option.dataset.fromSymbol = position.from_symbol;
          option.dataset.toSymbol = position.to_symbol;
          option.dataset.protocol = position.protocol;
          option.dataset.balance = position.balance;
          option.dataset.amountRaw = position.amount_raw || "";
          option.dataset.amountDecimals = String(position.amount_decimals ?? 0);
          option.dataset.amountSymbol = position.amount_symbol || "";
          positionEl.append(option);
        });

        let selected = positions.find((position) => String(position.id).toLowerCase() === currentId);
        if (!selected && lpRemove && pairMatch) {
          selected = positions.find((position) => {
            const symbols = [position.from_symbol.toUpperCase(), position.to_symbol.toUpperCase()];
            return symbols.includes(pairMatch[1].toUpperCase()) &&
              symbols.includes(pairMatch[2].toUpperCase());
          });
        }
        if (!selected && !lpRemove && currentSymbol) {
          selected = positions.find((position) =>
            position.from_symbol.toUpperCase() === currentSymbol ||
            position.to_symbol.toUpperCase() === currentSymbol
          );
        }
        if (!selected) selected = positions[0];
        positionEl.value = String(selected.id);
        renderPositionBalance();
        if (!positionSelectionRequired) {
          updateBtn.disabled = false;
          confirmBtn.disabled = !canConfirm;
        }
        return true;
      }

      const cacheKey = `${(wallet || "").toLowerCase()}:${positionProtocol}`;
      const cached = withdrawablePositionsCache.get(cacheKey);
      if (cached && cached.length) {
        applyPositions(cached);
      }

      try {
        const query = new URLSearchParams({ wallet, protocol: positionProtocol });
        const response = await fetch(`/api/withdrawable-positions?${query}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Positions unavailable");
        const positions = Array.isArray(data.positions) ? data.positions : [];
        if (!positions.length) throw new Error("No open positions found");
        withdrawablePositionsCache.set(cacheKey, positions);
        applyPositions(positions);

        const exactMatch = positions.some((position) =>
          String(position.id).toLowerCase() === currentId
        );
        if (currentId && !exactMatch && lpRemove) {
          markDirty();
          await rebuild();
        }
      } catch (_err) {
        if (!cached || !cached.length) {
          positionEl.replaceChildren();
          const option = document.createElement("option");
          option.value = currentId || currentSymbol;
          option.textContent = currentAction.summary || "Current position";
          option.dataset.fromSymbol = currentAction.to?.symbol || currentAction.from?.symbol || "";
          option.dataset.toSymbol = currentAction.to?.symbol || "";
          option.dataset.protocol = positionProtocol;
          option.dataset.balance = cardAmount(currentAction) || "Current position";
          positionEl.append(option);
          positionEl.disabled = true;
          renderPositionBalance();
        }
      }
    }

    async function rebuild() {
      errorEl.hidden = true;
      updateBtn.disabled = true;
      confirmBtn.disabled = true;
      try {
        const typedAmount = amountEl?.value?.trim() || "";
        const allRequested = ["all", "max", "yes"].includes(typedAmount.toLowerCase());
        const selected = selectedPosition();
        const body = {
          wallet,
          kind: currentAction.kind || currentAction.type,
          from_symbol: selected?.dataset.fromSymbol || fromEl?.value || "",
          to_symbol: selected?.dataset.toSymbol || toEl?.value || toggleEl?.value || currentAction.to?.amount || "",
          collateral_symbol: collateralEl?.value || "",
          amount: allRequested || (fullV4Repay && !amountEdited) ? "" : typedAmount,
          fraction: allRequested ? 1 : fraction,
          protocol: selected?.dataset.protocol || currentAction.protocol || "",
          position_id: selected?.value || "",
          balances: lastBalances,
        };
        const response = await fetch("/api/action/rebuild", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const result = await response.json();
        if (!response.ok || result.error) throw new Error(result.error || "Could not update transaction.");
        if (canceled) return;
        currentAction = result;
        needsRebuild = false;
        const fromText = currentAction.from ? `${currentAction.from.amount} ${currentAction.from.symbol}` : "—";
        const toText = currentAction.to ? `${currentAction.to.amount} ${currentAction.to.symbol}` : "—";
        card.querySelector(".action-from").textContent = fromText;
        card.querySelector(".action-to").textContent = toText;
        card.querySelector(".action-title").textContent = currentAction.summary || "Confirm on Base";
        card.querySelector(".action-route").textContent =
          currentAction.protocol || currentAction.route || currentAction.kind || "Base";
        if (fraction > 0 && amountEl) {
          if (lpRemove) renderPositionBalance();
          else amountEl.value = cardAmount(currentAction);
        }
        confirmBtn.disabled = positionSelectionRequired ||
          ((Boolean(currentAction.mock) || currentAction.route === "MOCK") && !demoEnabled());
      } catch (err) {
        if (canceled) return;
        errorEl.textContent = err?.message || String(err);
        errorEl.hidden = false;
        confirmBtn.disabled = needsRebuild;
      } finally {
        updateBtn.disabled = canceled;
      }
    }

    amountEl?.addEventListener("input", () => {
      fraction = 0;
      amountEdited = true;
      renderPositionBalance();
      markDirty();
    });
    fromEl?.addEventListener("change", () => {
      fraction = 0;
      amountEdited = true;
      markDirty();
      refreshEditorBalances();
      scheduleSwapRebuild();
    });
    toEl?.addEventListener("change", () => {
      fraction = 0;
      amountEdited = true;
      markDirty();
      refreshEditorBalances();
      scheduleSwapRebuild();
    });
    collateralEl?.addEventListener("change", () => {
      markDirty();
      refreshEditorBalances();
    });
    positionEl?.addEventListener("change", () => {
      positionSelectionRequired = false;
      fraction = 1;
      amountEdited = false;
      if (lpRemove) renderPositionBalance();
      else if (amountEl) amountEl.value = "";
      renderPositionBalance();
      updateBtn.disabled = false;
      markDirty();
    });
    toggleEl?.addEventListener("change", markDirty);
    card.querySelectorAll(".action-presets .gift-preset").forEach((button) => {
      button.addEventListener("click", async () => {
        markDirty();
        const selectedFraction = Number(button.dataset.frac);
        const isBorrow = /_borrow$/.test(currentAction.kind || "");
        if (isBorrow) {
          const base = Number(cardAmount(currentAction));
          if (!(base > 0)) {
            errorEl.textContent = "Enter a borrow amount before choosing a percentage.";
            errorEl.hidden = false;
            return;
          }
          amountEl.value = String(base * selectedFraction);
          fraction = 0;
        } else if (lpRemove) {
          fraction = selectedFraction;
          renderPositionBalance();
        } else if (withdrawAction) {
          fraction = selectedFraction;
          const option = selectedPosition();
          let baseBal = 0;
          if (option?.dataset.amountRaw) {
            const dec = Number(option.dataset.amountDecimals || 18);
            try {
              baseBal = Number(ethers.formatUnits(BigInt(option.dataset.amountRaw), dec));
            } catch (_) {}
          }
          if (baseBal <= 0) {
            const cached = getCachedTokenBalance(currentAction.to?.symbol || currentAction.from?.symbol || fromEl?.value);
            baseBal = Number(cached?.formatted || 0);
          }
          if (baseBal <= 0) {
            if (amountEl) amountEl.value = "0";
            confirmBtn.disabled = true;
          } else {
            const calculated = (baseBal * selectedFraction).toFixed(8).replace(/\.?0+$/, "");
            if (amountEl) amountEl.value = calculated;
          }
          renderPositionBalance();
        } else {
          fraction = selectedFraction;
          const fromSymbol = fromEl?.value || currentAction.from?.symbol;
          const cached = getCachedTokenBalance(fromSymbol);
          const bal = Number(cached?.formatted || 0);
          if (bal <= 0) {
            if (amountEl) amountEl.value = "0";
            confirmBtn.disabled = true;
          } else {
            const calculated = (bal * selectedFraction).toFixed(8).replace(/\.?0+$/, "");
            if (amountEl) amountEl.value = calculated;
          }
        }
        refreshEditorBalances();
        await rebuild();
      });
    });
    updateBtn.addEventListener("click", () => {
      window.clearTimeout(swapUpdateTimer);
      swapUpdateTimer = null;
      rebuild();
    });
    refreshEditorBalances();
    loadPositionOptions();

    cancelBtn.addEventListener("click", () => {
      canceled = true;
      window.clearTimeout(swapUpdateTimer);
      confirmBtn.disabled = true;
      cancelBtn.disabled = true;
      updateBtn.disabled = true;
      append("assistant", "Cancelled. No wallet prompt was sent.");
    });
    confirmBtn.addEventListener("click", () => {
      updateBtn.disabled = true;
      executeQuote(currentAction, confirmBtn, cancelBtn).catch((err) => {
        append("assistant", err?.shortMessage || err?.message || String(err), "error");
        updateBtn.disabled = false;
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
      });
    });
    appendHtml(card);
  }

  function renderBasketCard(basket) {
    const card = document.createElement("div");
    card.className = "quote-card basket-card";
    let legs = basket.legs || [];
    card.innerHTML = `
      <div class="quote-title">Basket on Base · <span class="basket-count">0/${legs.length} complete</span></div>
      <p class="muted basket-summary">${esc(basket.summary || "")}</p>
      <p class="muted basket-progress" aria-live="polite">0/${legs.length} swaps complete</p>
      <div class="basket-current-leg"></div>
      <p class="action-edit-error basket-error" hidden></p>
      <button type="button" class="action-update basket-update">Update basket</button>
      <div class="confirm-actions">
        <button type="button" class="confirm basket-confirm" ${legs.some((leg) => leg.ok) ? "" : "disabled"}>Confirm next swap</button>
        <button type="button" class="cancel basket-skip" ${legs.length > 1 ? "" : "hidden"}>Skip this swap</button>
        <button type="button" class="cancel basket-cancel">Cancel</button>
      </div>
    `;
    appendHtml(card);

    const confirmBtn = card.querySelector(".basket-confirm");
    const skipBtn = card.querySelector(".basket-skip");
    const cancelBtn = card.querySelector(".basket-cancel");
    const updateBtn = card.querySelector(".basket-update");
    const errorEl = card.querySelector(".basket-error");
    const progressEl = card.querySelector(".basket-progress");
    const countEl = card.querySelector(".basket-count");
    let fractions = legs.map(() => 0);
    const completedLegs = new Set();
    let needsRebuild = false;
    let canceled = false;
    let basketUpdateTimer = null;
    let currentLegIndex = legs.findIndex((leg) => leg.ok);
    if (currentLegIndex < 0 && legs.length) currentLegIndex = 0;
    const legContainer = card.querySelector(".basket-current-leg");

    const updateHeaderProgress = (extra = "") => {
      const completedCount = completedLegs.size;
      const total = legs.length;
      if (countEl) {
        countEl.textContent = `${completedCount}/${total} complete`;
      }
      if (progressEl) {
        progressEl.textContent = extra
          ? `${completedCount}/${total} swaps complete · ${extra}`
          : `${completedCount}/${total} swaps complete`;
      }
    };

    const markBasketDirty = () => {
      needsRebuild = true;
      confirmBtn.disabled = true;
    };

    function scheduleBasketRebuild() {
      window.clearTimeout(basketUpdateTimer);
      basketUpdateTimer = window.setTimeout(() => {
        basketUpdateTimer = null;
        if (!canceled && needsRebuild) void rebuild();
      }, 180);
    }

    function refreshEditorBalances() {
      const editor = legContainer.querySelector(".basket-leg-editor");
      if (!editor) return;
      const fromSelect = editor.querySelector(".basket-from");
      const toSelect = editor.querySelector(".basket-to");
      const fromBal = editor.querySelector(".action-balance");
      const toBal = editor.querySelector(".basket-to-balance");
      if (fromSelect && fromBal) {
        const c = getCachedTokenBalance(fromSelect.value);
        fromBal.textContent = c && c.formatted !== undefined && c.formatted !== null
          ? `Balance: ${c.formatted} ${c.symbol}`
          : "Balance: —";
      }
      if (toSelect && toBal) {
        const c = getCachedTokenBalance(toSelect.value);
        toBal.textContent = c && c.formatted !== undefined && c.formatted !== null
          ? `Balance: ${c.formatted} ${c.symbol}`
          : "Balance: —";
      }
    }

    async function rebuild() {
      errorEl.hidden = true;
      updateBtn.disabled = true;
      confirmBtn.disabled = true;
      if (skipBtn) skipBtn.disabled = true;
      try {
        const editor = legContainer.querySelector(".basket-leg-editor");
        if (!editor) return;
        const fromSelect = editor.querySelector(".basket-from");
        const toSelect = editor.querySelector(".basket-to");
        const amountInput = editor.querySelector(".basket-amount");
        const typedAmount = amountInput?.value?.trim() || "";
        const allRequested = ["all", "max", "yes"].includes(typedAmount.toLowerCase());

        const legFields = legs.map((leg, index) => {
          if (index !== currentLegIndex) {
            return {
              from_symbol: leg.from?.symbol || leg.symbol?.split("→")?.[0] || "USDC",
              to_symbol: leg.to?.symbol || leg.symbol?.split("→")?.[1] || "AAPLc",
              amount: leg.from?.amount || "",
              fraction: fractions[index] || 0,
            };
          }
          return {
            from_symbol: fromSelect?.value || leg.from?.symbol || "USDC",
            to_symbol: toSelect?.value || leg.to?.symbol || "AAPLc",
            amount: allRequested ? "" : typedAmount,
            fraction: allRequested ? 1 : (fractions[index] || 0),
          };
        });

        const response = await fetch("/api/action/rebuild", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ wallet, kind: "basket", legs: legFields, balances: lastBalances }),
        });
        const result = await response.json();
        if (!response.ok || result.error) throw new Error(result.error || "Could not update basket.");
        if (canceled) return;
        legs = result.legs || [];
        needsRebuild = false;

        card.querySelector(".basket-summary").textContent = result.summary || "";
        updateHeaderProgress();

        const currentLeg = legs[currentLegIndex];
        const quoteRow = legContainer.querySelector(".quote-row");
        if (quoteRow) {
          if (currentLeg?.ok) {
            quoteRow.className = "quote-row";
            quoteRow.innerHTML = `<span>${esc(currentLeg.from.amount)} ${esc(currentLeg.from.symbol)}</span>
              <span>→ ${esc(currentLeg.to.amount)} ${esc(currentLeg.to.symbol)}</span>
              <span class="muted">${esc(currentLeg.route || "")}${currentLeg.note ? " · " + esc(currentLeg.note) : ""}</span>`;
          } else {
            quoteRow.className = "quote-row error";
            quoteRow.innerHTML = `<span>${esc(currentLeg?.symbol || "?")}</span><span>${esc(currentLeg?.error || "no route")}</span>`;
          }
        }
        if (fractions[currentLegIndex] > 0 && amountInput && currentLeg?.from?.amount) {
          amountInput.value = currentLeg.from.amount;
        }
        confirmBtn.disabled = !currentLeg?.ok || completedLegs.has(currentLegIndex);
      } catch (err) {
        if (canceled) return;
        errorEl.textContent = err?.message || String(err);
        errorEl.hidden = false;
        confirmBtn.disabled = needsRebuild || !legs[currentLegIndex]?.ok || completedLegs.has(currentLegIndex);
      } finally {
        if (!canceled && currentLegIndex >= 0) {
          updateBtn.disabled = completedLegs.has(currentLegIndex);
          if (skipBtn) skipBtn.disabled = completedLegs.has(currentLegIndex);
        }
      }
    }

    const renderCurrentLeg = () => {
      if (currentLegIndex < 0) {
        legContainer.innerHTML = '<p class="basket-leg-status muted">No swaps are ready.</p>';
        confirmBtn.disabled = true;
        updateBtn.disabled = true;
        if (skipBtn) skipBtn.disabled = true;
        return;
      }
      const leg = legs[currentLegIndex];
      const display = leg?.ok
        ? `<div class="quote-row"><span>${esc(leg.from.amount)} ${esc(leg.from.symbol)}</span>
            <span>→ ${esc(leg.to.amount)} ${esc(leg.to.symbol)}</span>
            <span class="muted">${esc(leg.route || "")}${leg.note ? " · " + esc(leg.note) : ""}</span></div>`
        : `<div class="quote-row error"><span>${esc(leg?.symbol || "?")}</span><span>${esc(leg?.error || "no route")}</span></div>`;
      legContainer.innerHTML = `
        <div class="basket-leg">
          ${display}
          <p class="basket-leg-status muted" aria-live="polite"></p>
          ${basketLegEditor(leg)}
        </div>`;

      const editor = legContainer.querySelector(".basket-leg-editor");
      const fromSelect = editor.querySelector(".basket-from");
      const toSelect = editor.querySelector(".basket-to");
      const amountInput = editor.querySelector(".basket-amount");
      editor.querySelectorAll(".gift-preset").forEach((button) => {
        button.addEventListener("click", async () => {
          markBasketDirty();
          const frac = Number(button.dataset.frac);
          fractions[currentLegIndex] = frac;
          const fromSymbol = fromSelect?.value || "USDC";
          const cached = getCachedTokenBalance(fromSymbol);
          const bal = Number(cached?.formatted || 0);
          if (bal <= 0) {
            amountInput.value = "0";
            confirmBtn.disabled = true;
          } else {
            amountInput.value = (bal * frac).toFixed(8).replace(/\.?0+$/, "");
          }
          refreshEditorBalances();
          await rebuild();
        });
      });
      amountInput.addEventListener("input", () => {
        fractions[currentLegIndex] = 0;
        markBasketDirty();
      });
      fromSelect.addEventListener("change", () => {
        fractions[currentLegIndex] = 0;
        markBasketDirty();
        refreshEditorBalances();
        scheduleBasketRebuild();
      });
      toSelect.addEventListener("change", () => {
        fractions[currentLegIndex] = 0;
        markBasketDirty();
        refreshEditorBalances();
        scheduleBasketRebuild();
      });
      refreshEditorBalances();
      confirmBtn.disabled = !leg?.ok || needsRebuild || completedLegs.has(currentLegIndex);
      updateBtn.disabled = canceled || completedLegs.has(currentLegIndex);
      if (skipBtn) skipBtn.disabled = canceled || completedLegs.has(currentLegIndex);
    };
    renderCurrentLeg();

    updateBtn.addEventListener("click", () => {
      window.clearTimeout(basketUpdateTimer);
      basketUpdateTimer = null;
      void rebuild();
    });
    if (skipBtn) {
      skipBtn.addEventListener("click", () => {
        window.clearTimeout(basketUpdateTimer);
        basketUpdateTimer = null;
        if (currentLegIndex < 0 || completedLegs.has(currentLegIndex)) return;
        completedLegs.add(currentLegIndex);
        updateHeaderProgress();
        append("assistant", `Skipped swap ${currentLegIndex + 1}/${legs.length}.`);

        const nextIndex = legs.findIndex((_, idx) => !completedLegs.has(idx));
        if (nextIndex >= 0) {
          currentLegIndex = nextIndex;
          renderCurrentLeg();
        } else {
          updateHeaderProgress("all swaps processed");
          legContainer.innerHTML = '<p class="basket-leg-status muted">All swaps in this basket have been processed.</p>';
          confirmBtn.disabled = true;
          updateBtn.disabled = true;
          cancelBtn.disabled = true;
          skipBtn.disabled = true;
        }
      });
    }
    cancelBtn.addEventListener("click", () => {
      canceled = true;
      window.clearTimeout(basketUpdateTimer);
      confirmBtn.disabled = true;
      cancelBtn.disabled = true;
      updateBtn.disabled = true;
      if (skipBtn) skipBtn.disabled = true;
      append("assistant", "Basket cancelled.");
    });
    confirmBtn.addEventListener("click", () => {
      window.clearTimeout(basketUpdateTimer);
      updateBtn.disabled = true;
      if (skipBtn) skipBtn.disabled = true;
      void executeBasket(
        legs,
        confirmBtn,
        cancelBtn,
        completedLegs,
        progressEl,
        legContainer,
        updateBtn,
        (index) => {
          currentLegIndex = index;
          renderCurrentLeg();
        },
        skipBtn,
        (extra) => {
          updateHeaderProgress(extra);
        }
      );
    });
  }

  function basketLegEditor(leg) {
    const choices = (tokens || []).filter((token) => token?.address && token?.symbol);
    const optionMarkup = (selected) => choices.map((token) =>
      `<option value="${esc(token.symbol)}" ${token.symbol.toUpperCase() === String(selected || "").toUpperCase() ? "selected" : ""}>${esc(token.symbol)}</option>`
    ).join("");
    const fromSym = leg?.from?.symbol || leg?.symbol?.split("→")?.[0] || "USDC";
    const toSym = leg?.to?.symbol || leg?.symbol?.split("→")?.[1] || "AAPLc";

    const cachedFrom = getCachedTokenBalance(fromSym);
    const fromBalText = cachedFrom && cachedFrom.formatted !== undefined && cachedFrom.formatted !== null
      ? `Balance: ${cachedFrom.formatted} ${fromSym}`
      : "Balance: —";

    const cachedTo = getCachedTokenBalance(toSym);
    const toBalText = cachedTo && cachedTo.formatted !== undefined && cachedTo.formatted !== null
      ? `Balance: ${cachedTo.formatted} ${toSym}`
      : "Balance: —";

    return `<div class="basket-leg-editor action-editor">
      <label class="action-editor-field"><span>From token / stock</span>
        <select class="basket-from">${optionMarkup(fromSym)}</select>
        <small class="action-balance muted">${fromBalText}</small>
      </label>
      <label class="action-editor-field"><span>To token / stock</span>
        <select class="basket-to">${optionMarkup(toSym)}</select>
        <small class="basket-to-balance action-balance muted">${toBalText}</small>
      </label>
      <label class="action-editor-field"><span>Amount</span>
        <input class="basket-amount" type="text" inputmode="decimal" value="${esc(leg?.from?.amount || "")}">
        <div class="gift-presets action-presets">
          <button type="button" class="gift-preset" data-frac="0.25">25%</button>
          <button type="button" class="gift-preset" data-frac="0.5">50%</button>
          <button type="button" class="gift-preset" data-frac="0.75">75%</button>
          <button type="button" class="gift-preset" data-frac="1">100%</button>
        </div>
      </label>
    </div>`;
  }


  async function refreshBalanceLabel(select, label) {
    if (!select || !label) return;
    const cached = getCachedTokenBalance(select.value);
    if (cached && cached.formatted !== undefined && cached.formatted !== null) {
      label.textContent = `Balance: ${cached.formatted} ${cached.symbol}`;
    } else {
      label.textContent = "Balance: —";
    }
  }

  async function executeBasket(
    legs,
    confirmBtn,
    cancelBtn,
    completedLegs,
    progressEl,
    legContainer,
    updateBtn,
    selectLeg,
    skipBtn,
    onProgress
  ) {
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;
    if (skipBtn) skipBtn.disabled = true;
    const total = legs.length;
    for (let i = 0; i < total; i += 1) {
      if (completedLegs.has(i)) continue;
      const leg = legs[i];
      selectLeg(i);
      updateBtn.disabled = true;
      const statusEl = legContainer.querySelector(".basket-leg-status");

      if (!leg?.ok) {
        if (statusEl) {
          statusEl.classList.remove("muted");
          statusEl.classList.add("action-edit-error");
          statusEl.textContent = `Swap ${i + 1}/${total} is not ready: ${leg?.error || "no route"}. Fix it or skip this swap.`;
        }
        if (onProgress) onProgress("stopped");
        confirmBtn.disabled = true;
        cancelBtn.disabled = false;
        updateBtn.disabled = false;
        if (skipBtn) skipBtn.disabled = false;
        return;
      }

      if (onProgress) onProgress(`processing ${i + 1}/${total}`);
      if (statusEl) {
        statusEl.textContent = `Swap ${i + 1}/${total}: ${leg.from.symbol} → ${leg.to.symbol}. Confirm in your wallet.`;
      }
      try {
        await executeQuote(leg, confirmBtn, cancelBtn, {
          onStatus(message, href) {
            if (!statusEl) return;
            statusEl.replaceChildren(document.createTextNode(message));
            if (href) {
              const link = document.createElement("a");
              link.href = href;
              link.target = "_blank";
              link.rel = "noopener";
              link.textContent = " View on Basescan";
              statusEl.append(link);
            }
          },
        });
        completedLegs.add(i);
        if (onProgress) onProgress();
      } catch (err) {
        if (statusEl) {
          statusEl.classList.remove("muted");
          statusEl.classList.add("action-edit-error");
          statusEl.textContent = `Swap failed: ${humanTxError(err)}. Remaining swaps were not sent.`;
        }
        if (onProgress) onProgress("stopped");
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
        updateBtn.disabled = false;
        if (skipBtn) skipBtn.disabled = false;
        return;
      }
    }
    if (onProgress) onProgress("all swaps confirmed");
    progressEl.textContent = `Basket complete · ${completedLegs.size}/${total} swaps confirmed`;
    legContainer.innerHTML = '<p class="basket-leg-status muted">All swaps in this basket are confirmed.</p>';
    confirmBtn.disabled = true;
    updateBtn.disabled = true;
    cancelBtn.disabled = true;
    if (skipBtn) skipBtn.disabled = true;
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
      <p class="gift-error" hidden></p>
    `;
    appendHtml(card);

    const symbolEl = card.querySelector(".gift-symbol");
    const amountEl = card.querySelector(".gift-amount");
    const toEl = card.querySelector(".gift-to");
    const memoEl = card.querySelector(".gift-memo");
    const resolvedEl = card.querySelector(".gift-resolved");
    const balanceEl = card.querySelector(".gift-balance");
    const errorEl = card.querySelector(".gift-error");
    const confirmBtn = card.querySelector(".confirm");
    const cancelBtn = card.querySelector(".cancel");
    let resolvedTo = isHexAddress(action.to) ? action.to.toLowerCase() : "";
    let stockBalances = lastBalances.slice();

    function showGiftError(msg) {
      errorEl.hidden = !msg;
      errorEl.textContent = msg || "";
    }

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

    function selectedBalance() {
      const symbol = (symbolEl.value || "").toUpperCase();
      if (!symbol) return 0;
      const cached = getCachedTokenBalance(symbol);
      return cached ? Number(cached.formatted || 0) : 0;
    }

    function renderBalance() {
      if (!symbolEl.value) {
        balanceEl.textContent = "Balance: —";
        return;
      }
      const cached = getCachedTokenBalance(symbolEl.value);
      balanceEl.textContent = cached && cached.formatted !== undefined && cached.formatted !== null
        ? `Balance: ${cached.formatted} ${symbolEl.value}`
        : "Balance: —";
    }

    function refreshGiftButton() {
      showGiftError("");
      const amt = Number(amountEl.value);
      const bal = selectedBalance();
      if (symbolEl.value && amt > 0 && bal > 0 && amt > bal) {
        showGiftError(`Amount is above your ${symbolEl.value} balance (${bal}).`);
        confirmBtn.disabled = true;
        return;
      }
      confirmBtn.disabled = !Boolean(symbolEl.value && amt > 0 && resolvedTo);
    }

    function fillPercent(frac) {
      if (!symbolEl.value) return;
      const bal = selectedBalance();
      if (bal <= 0) {
        amountEl.value = "0";
        refreshGiftButton();
        return;
      }
      amountEl.value = (bal * frac).toFixed(8).replace(/\.?0+$/, "");
      refreshGiftButton();
    }

    function stockList() {
      return (tokens || []).filter((t) => t.kind === "stock");
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

    async function refreshSelectedBalance() {
      const symbol = symbolEl.value;
      if (!wallet || !symbol) return;
      const token = (tokens || []).find(
        (t) => (t.symbol || "").toUpperCase() === symbol.toUpperCase()
      );
      if (!token?.address) return;
      try {
        const contract = new ethers.Contract(token.address, ERC20_ABI, baseJsonProvider);
        const raw = await contract.balanceOf(wallet);
        const formatted = ethers.formatUnits(raw, token.decimals ?? 8);
        stockBalances = stockBalances.filter(
          (b) => (b.symbol || "").toUpperCase() !== symbol.toUpperCase()
        );
        stockBalances.push({ symbol: token.symbol, formatted, raw: raw.toString() });
        const idx = lastBalances.findIndex(
          (b) => (b.address && b.address.toLowerCase() === token.address.toLowerCase()) ||
            (b.symbol || "").toUpperCase() === symbol.toUpperCase()
        );
        const updatedItem = {
          symbol: token.symbol,
          name: token.name || token.symbol,
          address: token.address,
          decimals: token.decimals ?? 8,
          formatted,
          raw: raw.toString(),
        };
        if (idx >= 0) {
          lastBalances[idx] = updatedItem;
        } else {
          lastBalances.push(updatedItem);
        }
        renderBalance();
        if (presetFrac > 0 && !amountEl.value) fillPercent(presetFrac);
        refreshGiftButton();
      } catch (_err) {
        if (!selectedBalance()) balanceEl.textContent = "Balance: unavailable";
      }
    }

    populateSelect(stockList());
    renderBalance();
    if (presetFrac > 0) fillPercent(presetFrac);
    refreshGiftButton();

    if (!tokens.length) {
      loadTokens()
        .then(() => {
          populateSelect(stockList());
          refreshGiftButton();
          refreshSelectedBalance();
        })
        .catch(() => {
          resolvedEl.textContent = "Could not load stock list.";
        });
    } else {
      refreshSelectedBalance();
    }

    amountEl.addEventListener("input", refreshGiftButton);
    symbolEl.addEventListener("change", () => {
      renderBalance();
      refreshGiftButton();
      refreshSelectedBalance();
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
      showGiftError("");
      const amt = Number(amountEl.value);
      const bal = selectedBalance();
      if (amt > bal) {
        showGiftError(`Amount is above your ${symbolEl.value} balance (${bal}).`);
        return;
      }
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
        const msg = humanTxError(err);
        showGiftError(msg);
        append("assistant", msg, "error");
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

  async function executeQuote(action, confirmBtn, cancelBtn, { onStatus } = {}) {
    const eth = getInjectedProvider();
    if (!eth) throw new Error("Connect a wallet first.");
    const card = confirmBtn?.closest(".quote-card") || cancelBtn?.closest(".quote-card");
    if (confirmBtn) confirmBtn.disabled = true;
    if (cancelBtn) cancelBtn.disabled = true;

    let ok = false;

    try {
      await ensureBase();
      if (!wallet || !signedIn) {
        await connectWallet({ request: true, replay: false });
        if (!signedIn) throw new Error("Sign in with your wallet first.");
      }

      const provider = new ethers.BrowserProvider(eth);
      const signer = await provider.getSigner();
      const from = await signer.getAddress();
      if (from.toLowerCase() !== wallet.toLowerCase()) {
        await setWallet(from);
        signedIn = false;
        await connectWallet({ request: true, replay: false });
        if (!signedIn) throw new Error("Sign in with your wallet first.");
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
        "aave_v4_borrow",
        "aave_v4_withdraw",
        "aave_v4_collateral",
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
          const message = `Approve ${item.symbol || "token"} in your wallet.`;
          if (onStatus) onStatus(message);
          else append("assistant", message);
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
      }

      if (action.kind === "uni_lp_remove" || action.kind === "slip_lp_remove") {
        const id = BigInt(action.raw?.tokenId || 0);
        const liq = BigInt(action.from?.amountWei || action.raw?.liquidity || 0);
        const npmAddr = action.tx.to;
        const nft = new ethers.Contract(npmAddr, [
          "function ownerOf(uint256 tokenId) view returns (address)",
        ], signer);
        const owner = await nft.ownerOf(id);
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
      const txReq = {
        to: action.tx.to,
        data: skipSuffix ? data : withBuilderSuffix(data),
        value: action.tx.value && action.tx.value !== "0" ? action.tx.value : 0,
      };
      if (action.tx.gasLimit) {
        txReq.gasLimit = action.tx.gasLimit;
      } else if (action.tx.gas) {
        txReq.gasLimit = action.tx.gas;
      } else {
        try {
          const estimated = await signer.estimateGas(txReq);
          // Add 25% safety buffer so subcalls under EIP-150 don't run out of gas
          txReq.gasLimit = (estimated * 125n) / 100n;
        } catch (_) {
          // If estimation fails here, let signer.sendTransaction handle it
        }
      }
      const tx = await signer.sendTransaction(txReq);
      const submittedMessage = `Submitted ${tx.hash}`;
      if (onStatus) onStatus(submittedMessage);
      else append("assistant", submittedMessage);
      const receipt = await tx.wait();
      if (receipt?.status === 0) throw new Error("Transaction failed onchain.");
      playActionEffect(action, card);
      void renderBalancesPanel({ refresh: true, action });
      if (action.kind === "aave_v4_supply" && action.enable_collateral) {
        renderEnableCollateralCard(action.enable_collateral, action.from?.symbol);
      }

      const hash = receipt?.hash || tx.hash;
      const statusText = document.createTextNode("Transaction confirmed. ");
      const explorerLink = document.createElement("a");
      explorerLink.href = action.explorer || `https://basescan.org/tx/${hash}`;
      explorerLink.target = "_blank";
      explorerLink.rel = "noopener";
      explorerLink.textContent = "View on Basescan";
      if (onStatus) {
        onStatus("Transaction confirmed.", explorerLink.href);
      } else {
        const link = document.createElement("div");
        link.className = "msg assistant";
        link.append(statusText, explorerLink);
        appendHtml(link);
      }

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
      explorerLink.href = body.explorer || `https://basescan.org/tx/${hash}`;
      if (onStatus) onStatus("Trade recorded.", explorerLink.href);
      else statusText.textContent = "Trade recorded. ";
      await loadTradeHistory(wallet);
      ok = true;
    } catch (err) {
      if (confirmBtn) confirmBtn.disabled = false;
      if (cancelBtn) cancelBtn.disabled = false;
      throw err;
    } finally {
      if (!ok) {
        if (confirmBtn) confirmBtn.disabled = false;
        if (cancelBtn) cancelBtn.disabled = false;
      }
    }
  }

  function websocketChat(payload, onStatus) {
    return new Promise((resolve, reject) => {
      const socketUrl = new URL("/ws/chat", window.location.href);
      socketUrl.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const socket = new WebSocket(socketUrl);
      let complete = false;
      const timeout = setTimeout(() => fail(new Error("WebSocket chat timed out.")), 90000);

      function fail(error) {
        if (complete) return;
        complete = true;
        clearTimeout(timeout);
        socket.close();
        reject(error);
      }

      socket.addEventListener("open", () => {
        socket.send(JSON.stringify(payload));
      }, { once: true });
      socket.addEventListener("message", (event) => {
        let data;
        try {
          data = JSON.parse(event.data);
        } catch (_err) {
          fail(new Error("Invalid WebSocket chat response."));
          return;
        }
        if (data.type === "status") {
          onStatus(data.text || "Thinking…");
          return;
        }
        if (data.type === "error") {
          fail(new Error(data.error || "WebSocket chat failed."));
          return;
        }
        if (data.type === "final") {
          complete = true;
          clearTimeout(timeout);
          socket.close();
          resolve({ ...data, status: 200 });
        }
      });
      socket.addEventListener("error", () => {
        fail(new Error("WebSocket chat connection failed."));
      }, { once: true });
      socket.addEventListener("close", () => {
        if (!complete) fail(new Error("WebSocket chat closed before completing."));
      }, { once: true });
    });
  }

  async function requestChat(payload, onStatus) {
    try {
      return await websocketChat(payload, onStatus);
    } catch (_wsError) {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      return { ...data, status: response.status };
    }
  }

  async function sendChat(text, { skipUser = false } = {}) {
    if (!skipUser) append("user", text);
    if (sendBtn) sendBtn.disabled = true;
    const status = append("assistant", "Thinking", "thinking");
    const setThinkingText = (text) => {
      status.textContent = String(text || "").replace(/(?:\.{3}|…)\s*$/, "");
    };
    let slow;
    let gathering;
    let finalizing;
    try {
      const activeWallet = (wallet && signedIn) ? wallet : null;
      const balances = activeWallet ? lastBalances : [];
      slow = setTimeout(() => {
        if (status.isConnected) setThinkingText("Still thinking");
      }, 5000);
      gathering = setTimeout(() => {
        if (status.isConnected) setThinkingText("Gathering resources");
      }, 15000);
      finalizing = setTimeout(() => {
        if (status.isConnected) setThinkingText("Finalizing");
      }, 25000);
      const data = await requestChat({
        message: text,
        wallet: activeWallet,
        thread_id: sessionThread(),
        balances,
      }, (text) => {
        if (status.isConnected) setThinkingText(text);
      });
      if (data.status === 401) {
        signedIn = false;
        paintWalletButton();
        status.textContent = data.error || "Sign in with your wallet first.";
        status.classList.remove("thinking");
        status.classList.add("error");
        return;
      }
      if (data.status && data.status >= 400) {
        status.textContent = data.error || "Chat failed";
        status.classList.remove("thinking");
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
      } else if (data.action?.type === "basket") {
        renderBasketCard(data.action);
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
  balancesToggle?.addEventListener("click", () => {
    if (balancesPanel?.classList.contains("is-open")) closeBalances();
    else openBalances();
  });
  balancesBackdrop?.addEventListener("click", closeBalances);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeHistory();
      closeBalances();
      if (walletCopyPopup) walletCopyPopup.hidden = true;
      walletBtn?.setAttribute("aria-expanded", "false");
    }
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
    loadTokens().catch(() => { });
    renderBalancesPanel();
    if (getInjectedProvider()) {
      try {
        await connectWallet({
          request: false,
          replay: false,
          checkCachedBalances: true,
        });
      } catch (_err) {
        persistWallet(null);
      }
    }
    const pending = sessionStorage.getItem("stocktalk.pending_prompt");
    if (pending) {
      sessionStorage.removeItem("stocktalk.pending_prompt");
      sendChat(landingPromptText(pending));
    }
  })();
}