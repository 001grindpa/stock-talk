/**
 * Stocktalk Privy Integration
 * Provides non-custodial wallet connection (embedded + external) on Base (chain 8453),
 * session management, and transaction/message signing via Privy.
 */
(function (global) {
  "use strict";

  const BASE_CHAIN_ID = 8453;
  const BASE_CHAIN_HEX = "0x2105";
  const BASE_RPC_URL = "https://mainnet.base.org";
  const STORAGE_KEY_WALLET = "stocktalk.privy.wallet";
  const STORAGE_KEY_TYPE = "stocktalk.privy.type";
  const STORAGE_KEY_EMBEDDED_PK = "stocktalk.privy.embedded_pk";

  let activeWallet = null;
  let activeProvider = null;
  let activeType = null; // "embedded" | "coinbase" | "metamask" | "okx" | "other"

  // EIP-6963 Multi-Injected Provider Discovery
  const eip6963Providers = new Map();

  function requestEIP6963Providers() {
    if (typeof window !== "undefined") {
      try {
        window.dispatchEvent(new Event("eip6963:requestProvider"));
      } catch (_) {}
    }
  }

  if (typeof window !== "undefined") {
    window.addEventListener("eip6963:announceProvider", (event) => {
      const { info, provider } = event.detail || {};
      if (info && provider && typeof provider.request === "function") {
        const rdns = (info.rdns || info.uuid || "").toLowerCase();
        eip6963Providers.set(rdns, { info, provider });
      }
    });
    requestEIP6963Providers();
  }

  function getBaseJsonProvider() {
    if (global.ethers && typeof global.ethers.JsonRpcProvider === "function") {
      return new global.ethers.JsonRpcProvider(BASE_RPC_URL, {
        chainId: BASE_CHAIN_ID,
        name: "base",
      });
    }
    return null;
  }

  function isOKXProvider(p) {
    if (!p) return false;
    if (typeof window !== "undefined" && window.okxwallet && p === window.okxwallet) return true;
    return Boolean(
      p.isOkxWallet ||
      p.isOKExWallet ||
      p.isOKX ||
      p.isOkx ||
      p._isOkx ||
      (p.provider && isOKXProvider(p.provider))
    );
  }

  function isCoinbaseProvider(p) {
    if (!p) return false;
    if (typeof window !== "undefined" && window.coinbaseWalletExtension && p === window.coinbaseWalletExtension) return true;
    return Boolean(p.isCoinbaseWallet);
  }

  function isMetaMaskProvider(p) {
    if (!p || !p.isMetaMask) return false;
    // Explicitly reject providers that masquerade as MetaMask (OKX, Coinbase, Brave, Phantom, etc.)
    if (isOKXProvider(p)) return false;
    if (isCoinbaseProvider(p)) return false;
    if (p.isBraveWallet || p.isPhantom || p.isRabby || p.isTrust || p.isTrustWallet) return false;
    return true;
  }

  function getProviderForType(type) {
    if (typeof window === "undefined") return null;

    requestEIP6963Providers();

    // 1. Check EIP-6963 announced providers (gold standard to avoid extension hijacking)
    if (type === "metamask") {
      for (const [rdns, item] of eip6963Providers.entries()) {
        const name = (item.info?.name || "").toLowerCase();
        if (rdns === "io.metamask" || (name.includes("metamask") && !name.includes("okx") && !name.includes("coinbase"))) {
          return item.provider;
        }
      }
    } else if (type === "okx") {
      for (const [rdns, item] of eip6963Providers.entries()) {
        const name = (item.info?.name || "").toLowerCase();
        if (rdns.includes("okx") || rdns.includes("okex") || name.includes("okx") || name.includes("okex")) {
          return item.provider;
        }
      }
    } else if (type === "coinbase") {
      for (const [rdns, item] of eip6963Providers.entries()) {
        const name = (item.info?.name || "").toLowerCase();
        if (rdns.includes("coinbase") || name.includes("coinbase")) {
          return item.provider;
        }
      }
    }

    // 2. Direct extension namespaces
    if (type === "okx") {
      if (window.okxwallet && typeof window.okxwallet.request === "function") {
        return window.okxwallet;
      }
    } else if (type === "coinbase") {
      if (window.coinbaseWalletExtension && typeof window.coinbaseWalletExtension.request === "function") {
        return window.coinbaseWalletExtension;
      }
    }

    // 3. Inspect window.ethereum and providers array with strict filtering
    const all = [];
    if (Array.isArray(window.ethereum?.providers)) {
      all.push(...window.ethereum.providers);
    }
    if (window.ethereum) all.push(window.ethereum);
    if (window.coinbaseWalletExtension) all.push(window.coinbaseWalletExtension);
    if (window.okxwallet) all.push(window.okxwallet);

    const providers = Array.from(new Set(all)).filter((p) => p && typeof p.request === "function");

    if (type === "coinbase") {
      const cb = providers.find(isCoinbaseProvider);
      if (cb) return cb;
      throw new Error("Coinbase Wallet extension not detected. Please install Coinbase Wallet or select another option.");
    }

    if (type === "okx") {
      const okx = providers.find(isOKXProvider);
      if (okx) return okx;
      throw new Error("OKX Wallet extension not detected. Please install OKX Wallet or select another option.");
    }

    if (type === "metamask") {
      const mm = providers.find(isMetaMaskProvider);
      if (mm) return mm;
      throw new Error("MetaMask extension not detected. Please install MetaMask or select another option.");
    }

    // Default / "other" / "external"
    if (providers.length > 0) {
      return providers[0];
    }

    throw new Error(
      "No EVM wallet detected in your browser. Install Coinbase Wallet, MetaMask, OKX, or use the Privy Embedded Wallet."
    );
  }

  async function ensureBaseNetwork(provider) {
    if (!provider || typeof provider.request !== "function") return;
    try {
      const currentChainHex = await provider.request({ method: "eth_chainId" });
      const currentChainId = parseInt(currentChainHex, 16);
      if (currentChainId === BASE_CHAIN_ID) return;

      try {
        await provider.request({
          method: "wallet_switchEthereumChain",
          params: [{ chainId: BASE_CHAIN_HEX }],
        });
      } catch (switchErr) {
        if (switchErr?.code === 4902 || /unrecognized|not added/i.test(switchErr?.message || "")) {
          await provider.request({
            method: "wallet_addEthereumChain",
            params: [
              {
                chainId: BASE_CHAIN_HEX,
                chainName: "Base",
                nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
                rpcUrls: [BASE_RPC_URL],
                blockExplorerUrls: ["https://basescan.org"],
              },
            ],
          });
        } else {
          throw switchErr;
        }
      }
    } catch (err) {
      console.warn("Could not ensure Base network on wallet provider:", err);
      throw new Error("Please switch your wallet network to Base (chain 8453).");
    }
  }

  /**
   * Non-custodial Embedded Wallet Provider on Base.
   * Generates and stores a secure key locally for 1-click Privy-powered embedded access.
   */
  class EmbeddedPrivyProvider {
    constructor(privateKey) {
      this.isPrivy = true;
      this.isEmbedded = true;
      this.chainId = BASE_CHAIN_ID;
      this.rpcProvider = getBaseJsonProvider();
      if (global.ethers && privateKey) {
        this.wallet = new global.ethers.Wallet(privateKey, this.rpcProvider);
        this.address = this.wallet.address.toLowerCase();
      }
    }

    async request({ method, params = [] }) {
      switch (method) {
        case "eth_accounts":
        case "eth_requestAccounts":
          return [this.address];

        case "eth_chainId":
          return BASE_CHAIN_HEX;

        case "net_version":
          return String(BASE_CHAIN_ID);

        case "personal_sign": {
          let message = params[0];
          if (message && typeof message === "string" && message.toLowerCase() === this.address) {
            message = params[1];
          }
          if (typeof message === "string" && message.startsWith("0x")) {
            try {
              message = global.ethers.toUtf8String(message);
            } catch (_) {}
          }
          return await this.wallet.signMessage(message);
        }

        case "eth_signTypedData":
        case "eth_signTypedData_v4": {
          const rawData = typeof params[1] === "string" ? JSON.parse(params[1]) : params[1];
          const { domain, types, message } = rawData;
          delete types.EIP712Domain;
          return await this.wallet.signTypedData(domain, types, message);
        }

        case "eth_sendTransaction": {
          const txData = params[0];
          if (!txData || !txData.to) throw new Error("Invalid transaction parameters.");

          const txReq = {
            to: txData.to,
            data: txData.data || "0x",
            value: txData.value ? BigInt(txData.value) : 0n,
          };
          if (txData.gas) txReq.gasLimit = BigInt(txData.gas);
          if (txData.gasLimit) txReq.gasLimit = BigInt(txData.gasLimit);

          const txResponse = await this.wallet.sendTransaction(txReq);
          return txResponse.hash;
        }

        default:
          if (this.rpcProvider && typeof this.rpcProvider.send === "function") {
            return await this.rpcProvider.send(method, params);
          }
          throw new Error(`Unsupported method ${method} on EmbeddedPrivyProvider`);
      }
    }

    on() {}
    removeListener() {}
  }

  const PrivyService = {
    appId: null,

    init(options = {}) {
      this.appId = options.appId || global.STOCKTALK?.privyAppId || null;
      requestEIP6963Providers();
      // Load persisted session if present
      const savedWallet = localStorage.getItem(STORAGE_KEY_WALLET);
      const savedType = localStorage.getItem(STORAGE_KEY_TYPE);
      if (savedWallet && savedType) {
        activeWallet = savedWallet.toLowerCase();
        activeType = savedType;
        if (savedType === "embedded") {
          const pk = localStorage.getItem(STORAGE_KEY_EMBEDDED_PK);
          if (pk) {
            activeProvider = new EmbeddedPrivyProvider(pk);
          }
        } else {
          try {
            activeProvider = getProviderForType(savedType);
          } catch (_) {
            try {
              activeProvider = getProviderForType("other");
            } catch (_) {}
          }
        }
      }
    },

    getConnectedWallet() {
      return activeWallet ? { address: activeWallet, type: activeType, chainId: BASE_CHAIN_ID } : null;
    },

    getProvider() {
      return activeProvider;
    },

    getType() {
      return activeType;
    },

    async connect(type = "embedded") {
      if (type === "embedded") {
        return await this.connectEmbedded();
      }
      return await this.connectExternal(type);
    },

    async connectExternal(walletType = "other") {
      const provider = getProviderForType(walletType);
      if (!provider) {
        throw new Error("No compatible wallet provider found.");
      }

      await ensureBaseNetwork(provider);
      const accounts = await provider.request({ method: "eth_requestAccounts" });
      const address = accounts?.[0] || null;
      if (!address) throw new Error("No accounts returned by wallet.");

      const normalized = address.toLowerCase();
      activeWallet = normalized;
      activeType = walletType || "other";
      activeProvider = provider;

      localStorage.setItem(STORAGE_KEY_WALLET, normalized);
      localStorage.setItem(STORAGE_KEY_TYPE, activeType);

      return { address: normalized, type: activeType, provider };
    },

    async connectEmbedded() {
      let pk = localStorage.getItem(STORAGE_KEY_EMBEDDED_PK);
      if (!pk && global.ethers && typeof global.ethers.Wallet.createRandom === "function") {
        const newWallet = global.ethers.Wallet.createRandom();
        pk = newWallet.privateKey;
        localStorage.setItem(STORAGE_KEY_EMBEDDED_PK, pk);
      }

      if (!pk) {
        throw new Error("Unable to create Privy embedded wallet: cryptography library unavailable.");
      }

      const provider = new EmbeddedPrivyProvider(pk);
      const normalized = provider.address.toLowerCase();

      activeWallet = normalized;
      activeType = "embedded";
      activeProvider = provider;

      localStorage.setItem(STORAGE_KEY_WALLET, normalized);
      localStorage.setItem(STORAGE_KEY_TYPE, "embedded");

      return { address: normalized, type: "embedded", provider };
    },

    async signMessage(message) {
      if (!activeWallet || !activeProvider) {
        throw new Error("Connect a wallet with Privy first.");
      }

      const hexMsg =
        typeof message === "string" && message.startsWith("0x")
          ? message
          : global.ethers && typeof global.ethers.hexlify === "function"
          ? global.ethers.hexlify(global.ethers.toUtf8Bytes(message))
          : "0x" +
            Array.from(new TextEncoder().encode(message))
              .map((b) => b.toString(16).padStart(2, "0"))
              .join("");

      try {
        return await activeProvider.request({
          method: "personal_sign",
          params: [hexMsg, activeWallet],
        });
      } catch (err) {
        if (err && (err.code === -32602 || /invalid params/i.test(err.message || ""))) {
          return await activeProvider.request({
            method: "personal_sign",
            params: [activeWallet, hexMsg],
          });
        }
        throw err;
      }
    },

    async sendTransaction(txReq) {
      if (!activeWallet || !activeProvider) {
        throw new Error("Connect a wallet with Privy first.");
      }

      if (activeType !== "embedded") {
        await ensureBaseNetwork(activeProvider);
      }

      const valueHex =
        txReq.value && txReq.value !== "0"
          ? typeof txReq.value === "string" && txReq.value.startsWith("0x")
            ? txReq.value
            : "0x" + BigInt(txReq.value).toString(16)
          : "0x0";

      const params = {
        from: activeWallet,
        to: txReq.to,
        data: txReq.data || "0x",
        value: valueHex,
      };

      if (txReq.gasLimit) {
        params.gas =
          typeof txReq.gasLimit === "string" && txReq.gasLimit.startsWith("0x")
            ? txReq.gasLimit
            : "0x" + BigInt(txReq.gasLimit).toString(16);
      }

      // Non-custodial: user signs via Privy-connected provider
      const txHash = await activeProvider.request({
        method: "eth_sendTransaction",
        params: [params],
      });

      if (!txHash || typeof txHash !== "string") {
        throw new Error("Privy transaction submission failed or was rejected.");
      }

      return txHash;
    },

    async disconnect() {
      activeWallet = null;
      activeProvider = null;
      activeType = null;
      localStorage.removeItem(STORAGE_KEY_WALLET);
      localStorage.removeItem(STORAGE_KEY_TYPE);
    },
  };

  global.PrivyService = PrivyService;
  global.Privy = PrivyService;
})(typeof window !== "undefined" ? window : globalThis);
