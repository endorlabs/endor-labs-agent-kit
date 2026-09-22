#!/usr/bin/env python3
"""Package the Endor AURI Agent source for Agent Engine / Marketplace.

Based on Google's marketplace-agents-package `package_agent.py`, adapted for our
two-package layout: the agent (`endor_oss`) imports the shared core (`service`),
so BOTH must sit at the root of the archive (same approach our
adk/deploy_agent_engine.py proved). The reference packager only handles a single
package; this one stages both.

Produces:
  - assets/source.tar.gz   with endor_oss/ and service/ at the top level,
    endor_oss/app.py (Agent Engine entry point), endor_oss/requirements.txt
  - agent_config.auto.tfvars   with agent_package_name = "endor_oss"

Run from this deploy/ directory before `terraform apply`:
    python3 package_agent.py
"""

from __future__ import annotations

import argparse
import os
import shutil
import tarfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_GE_ROOT = os.path.dirname(os.path.dirname(_HERE))  # .../gemini-enterprise

_IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", ".git", ".venv", ".idea", ".vscode",
    "tests", "test", ".adk", ".pytest_cache",
)

# Pinned for reproducible Agent Engine builds. The archive is source (no local
# pickling), so these only need to be a working, mutually compatible set.
_REQUIREMENTS = """\
google-cloud-aiplatform[agent_engines,adk]==1.148.1
google-adk==1.14.1
google-genai==1.75.0
pydantic==2.13.4
httpx==0.28.1
"""

_APP_PY = """\
from vertexai.agent_engines import AdkApp
from .agent import root_agent

agent = AdkApp(agent=root_agent)
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Package Endor AURI Agent for Agent Engine.")
    ap.add_argument("--agent-source", default=os.path.join(_GE_ROOT, "adk", "endor_oss"),
                    help="Path to the ADK agent package (default: ../../adk/endor_oss).")
    ap.add_argument("--service-source", default=os.path.join(_GE_ROOT, "service"),
                    help="Path to the shared service package (default: ../../service).")
    ap.add_argument("--package-name", default="endor_oss",
                    help="Top-level agent package name / entrypoint (default: endor_oss).")
    ap.add_argument("--output", default=os.path.join(_HERE, "assets", "source.tar.gz"))
    args = ap.parse_args()

    for label, path in (("agent", args.agent_source), ("service", args.service_source)):
        if not os.path.isdir(path):
            print(f"Error: {label} source directory not found: {path}")
            return 1

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    staging = os.path.join(_HERE, "_temp_package")
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)
    try:
        # Two top-level packages at the archive root: the agent + the shared core.
        pkg_dir = os.path.join(staging, args.package_name)
        shutil.copytree(args.agent_source, pkg_dir, ignore=_IGNORE)
        shutil.copytree(args.service_source, os.path.join(staging, "service"), ignore=_IGNORE)

        # Agent Engine entry point (endor_oss.app:agent) + runtime requirements.
        with open(os.path.join(pkg_dir, "app.py"), "w") as f:
            f.write(_APP_PY)
        with open(os.path.join(pkg_dir, "requirements.txt"), "w") as f:
            f.write(_REQUIREMENTS)

        with tarfile.open(args.output, "w:gz") as tar:
            tar.add(pkg_dir, arcname=args.package_name)
            tar.add(os.path.join(staging, "service"), arcname="service")

        with open(os.path.join(_HERE, "agent_config.auto.tfvars"), "w") as f:
            f.write(f'agent_package_name = "{args.package_name}"\n')

        print(f"Packaged '{args.package_name}' + 'service' -> {args.output}")
        print(f"Wrote agent_config.auto.tfvars (agent_package_name={args.package_name})")
        return 0
    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
