#!/usr/bin/env python3
"""Path B — upload the exported ontology CSVs into a Fabric Lakehouse's OneLake Files
area, from your machine or CI (NOT from the build sandbox — needs auth + network to
onelake.dfs.fabric.microsoft.com).

Prereqs
-------
  pip install azure-identity azure-storage-file-datalake
  - az login  (your account)  OR  set FABRIC_TENANT_ID / FABRIC_CLIENT_ID /
    FABRIC_CLIENT_SECRET for a service principal that:
      * is a Contributor/Admin on the workspace, and
      * is allowed by the tenant setting "Service principals can use Fabric APIs".
  - A Lakehouse already created in the workspace.

Run
---
  export FABRIC_WORKSPACE="My Workspace"        # workspace name or GUID
  export FABRIC_LAKEHOUSE="enterprisecertiq"    # lakehouse name (without .Lakehouse)
  python scripts/export_fabric_tables.py        # produce the CSVs first
  python scripts/fabric/upload_to_onelake.py

Then materialize Delta tables: run scripts/fabric/load_lakehouse.py inside a Fabric
notebook, or use the Lakehouse UI "Load to Tables (overwrite)" on Files/fabric_export.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ONELAKE = "https://onelake.dfs.fabric.microsoft.com"
ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "backend" / "data" / "fabric_export"
DEST_DIR = "fabric_export"  # under <lakehouse>.Lakehouse/Files/


def _credential():
    """Service principal when FABRIC_* creds are set, else your az-login identity."""
    from azure.identity import ClientSecretCredential, DefaultAzureCredential
    tid, cid, sec = (os.getenv("FABRIC_TENANT_ID"), os.getenv("FABRIC_CLIENT_ID"),
                     os.getenv("FABRIC_CLIENT_SECRET"))
    if tid and cid and sec:
        print("Auth: service principal (FABRIC_* env)")
        return ClientSecretCredential(tid, cid, sec)
    print("Auth: DefaultAzureCredential (az login)")
    return DefaultAzureCredential()


def main() -> int:
    workspace = os.getenv("FABRIC_WORKSPACE")
    lakehouse = os.getenv("FABRIC_LAKEHOUSE")
    if not workspace or not lakehouse:
        print("ERROR: set FABRIC_WORKSPACE and FABRIC_LAKEHOUSE", file=sys.stderr)
        return 2
    files = sorted(SRC.glob("*.csv"))
    if not files:
        print(f"ERROR: no CSVs in {SRC} — run scripts/export_fabric_tables.py first", file=sys.stderr)
        return 2

    from azure.storage.filedatalake import DataLakeServiceClient

    service = DataLakeServiceClient(account_url=ONELAKE, credential=_credential())
    # In OneLake the "filesystem" is the workspace; the path is <lakehouse>.Lakehouse/Files/...
    fs = service.get_file_system_client(workspace)
    base = f"{lakehouse}.Lakehouse/Files/{DEST_DIR}"

    print(f"Uploading {len(files)} files → {workspace}/{base}/")
    for path in files:
        file_client = fs.get_file_client(f"{base}/{path.name}")
        data = path.read_bytes()
        file_client.upload_data(data, overwrite=True)
        print(f"  {path.name:<28} {len(data):>6} bytes")

    print("Done. Now materialize Delta tables (notebook scripts/fabric/load_lakehouse.py "
          "or Lakehouse UI → Load to Tables).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
