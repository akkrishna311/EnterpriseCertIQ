"""
Foundry Local model setup script.

Downloads and loads the configured model so the inference server
is ready before the FastAPI backend starts accepting requests.

Usage:
    python3 scripts/setup_foundry.py
    python3 scripts/setup_foundry.py --alias phi-4-mini
    python3 scripts/setup_foundry.py --alias qwen2.5-0.5b
    python3 scripts/setup_foundry.py --list        # list available models
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
from urllib.parse import urlparse

# Ensure project root is on PYTHONPATH when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _list_models():
    try:
        from foundry_local_sdk import FoundryLocalManager, Configuration
        cfg = Configuration(app_name="enterprisecertiq")
        FoundryLocalManager.initialize(cfg)
        mgr = FoundryLocalManager.instance
        catalog = mgr.catalog
        print("\nAvailable models in Foundry Local catalog:")
        print("-" * 50)
        for model in catalog.models:
            alias = getattr(model, 'alias', getattr(model, 'id', 'unknown'))
            print(f"  {alias}")
        print()
    except Exception as e:
        print(f"[warn] Could not list models: {e}")
        print("Make sure Foundry Local is installed: pip install foundry-local-sdk")
        sys.exit(1)


def _normalize_web_service_url(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "127.0.0.1"
    if parsed.port:
        return f"{scheme}://{host}:{parsed.port}"
    if parsed.netloc:
        return f"{scheme}://{parsed.netloc}"
    return endpoint.rstrip("/")


def _build_manager(start_web_service: bool = False, endpoint: str | None = None):
    from foundry_local_sdk import FoundryLocalManager, Configuration

    cfg_kwargs = {"app_name": "enterprisecertiq"}
    if start_web_service:
        cfg_kwargs["web"] = Configuration.WebService(
            urls=_normalize_web_service_url(endpoint or "http://127.0.0.1:5273")
        )

    cfg = Configuration(**cfg_kwargs)
    FoundryLocalManager.initialize(cfg)
    return FoundryLocalManager.instance


def _setup_model(alias: str, serve: bool = False, endpoint: str | None = None):
    print(f"[setup_foundry] Initialising Foundry Local SDK …")

    try:
        from foundry_local_sdk import FoundryLocalManager
    except ImportError:
        print("[error] foundry-local-sdk not installed.")
        print("        Run:  pip install foundry-local-sdk")
        sys.exit(1)

    try:
        mgr = _build_manager(start_web_service=serve, endpoint=endpoint)
    except Exception as e:
        print(f"[error] Could not initialise Foundry Local Manager: {e}")
        print("        Make sure Foundry Local is installed on your system.")
        print("        See: https://learn.microsoft.com/azure/foundry-local/get-started")
        sys.exit(1)

    if serve:
        try:
            mgr.start_web_service()
            print(f"[setup_foundry] Web service listening on: {', '.join(mgr.urls or [])}")
        except Exception as e:
            print(f"[error] Could not start Foundry Local web service: {e}")
            sys.exit(1)

    print(f"[setup_foundry] Looking up model alias '{alias}' …")
    try:
        model = mgr.catalog.get_model(alias)
        if model is None:
            print(f"[error] Model alias '{alias}' not found in catalog.")
            print("        Run with --list to see available models.")
            sys.exit(1)
    except Exception as e:
        print(f"[error] Catalog lookup failed: {e}")
        sys.exit(1)

    # Download if not already cached
    already_cached = False
    try:
        already_cached = model.is_cached()
    except Exception:
        pass

    if not already_cached:
        print(f"[setup_foundry] Downloading '{alias}' (this may take a few minutes) …")
        try:
            def _progress(pct: float):
                bar_len = 30
                filled = int(bar_len * pct / 100)
                bar = "█" * filled + "░" * (bar_len - filled)
                print(f"\r  [{bar}] {pct:.1f}%", end="", flush=True)

            model.download(_progress)
            print()  # newline after progress bar
        except Exception as e:
            print(f"\n[error] Download failed: {e}")
            sys.exit(1)
    else:
        print(f"[setup_foundry] '{alias}' already cached — skipping download.")

    if not serve:
        print(f"[setup_foundry] Cached model '{alias}' is ready.")
        return

    print(f"[setup_foundry] Loading '{alias}' into Foundry Local …")
    try:
        model.load()
    except Exception as e:
        print(f"[error] model.load() failed: {e}")
        sys.exit(1)

    # Also load the reasoning model into the SAME serving manager so the
    # /v1 endpoint can serve it. (Loading via a separate process/manager does
    # not register with this web service.) The Critic runs on this model.
    reasoning_alias = os.environ.get("FOUNDRY_LOCAL_REASONING_ALIAS", "").strip()
    if not reasoning_alias:
        try:
            from config.settings import get_settings
            reasoning_alias = get_settings().foundry_local_reasoning_alias.strip()
        except Exception:
            reasoning_alias = ""

    if reasoning_alias and reasoning_alias != alias:
        print(f"[setup_foundry] Loading reasoning model '{reasoning_alias}' …")
        try:
            r_model = mgr.catalog.get_model(reasoning_alias)
            if not r_model.is_cached:
                print(f"[setup_foundry] Downloading '{reasoning_alias}' (one-time) …")
                r_model.download(lambda pct: print(f"\r  [{pct:.1f}%]", end="", flush=True))
                print()
            r_model.load()
            print(f"[setup_foundry] Reasoning model '{reasoning_alias}' loaded.")
        except Exception as e:
            print(f"[warn] Could not load reasoning model '{reasoning_alias}': {e}")
            print("       The Critic will fall back to the default model.")

    print(f"[setup_foundry] '{alias}' is loaded and serving. Press Ctrl+C to stop.")
    signal.pause()


def main():
    parser = argparse.ArgumentParser(description="Foundry Local model setup")
    parser.add_argument("--alias", default=None, help="Model alias to download and load")
    parser.add_argument("--list", action="store_true", help="List available models")
    parser.add_argument("--serve", action="store_true", help="Start the local web service and keep the model loaded")
    parser.add_argument("--endpoint", default=None, help="OpenAI-compatible endpoint to bind when using --serve")
    args = parser.parse_args()

    if args.list:
        _list_models()
        return

    # Resolve alias: CLI arg → env var → config default
    alias = args.alias
    if not alias:
        alias = os.environ.get("FOUNDRY_LOCAL_MODEL_ALIAS", "")
    if not alias:
        try:
            from config.settings import get_settings
            alias = get_settings().foundry_local_model_alias
        except Exception:
            alias = "phi-4-mini"

    _setup_model(alias, serve=args.serve, endpoint=args.endpoint)


if __name__ == "__main__":
    main()
