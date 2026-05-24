# Endor Labs Agent Kit Context

Endor Labs Agent Kit is a source-first catalog for portable Endor workflow agents. This context records the project language used when discussing recipe authoring, host publication, generated artifacts, and installable catalog outputs.

## Language

**Source Recipe**:
The maintainer-authored definition for one agent under `source/agents/<agent>/recipe.yaml`, together with its nearby source files such as instructions, eval cases, actions, and architecture diagram. One Source Recipe can publish zero or more Host Artifact Bundles.
_Avoid_: generated recipe, catalog recipe

**Host**:
An AI coding environment that can receive generated agent artifacts, such as Claude Code, Claude Managed Agents, or Codex. A Host determines artifact shape, install path, tool permissions, and README setup language.
_Avoid_: runtime, provider, platform

**Host Artifact Bundle**:
The complete generated, installable artifact set for one Source Recipe on one Host. It includes the host-native prompt or skill files, generated agent README, optional action metadata, optional architecture diagram, optional setup guide, and manifest record.
_Avoid_: output folder, generated files

**Bundle Record**:
The internal structured result returned by a Host Adapter after publishing one Host Artifact Bundle. It carries written paths, manifest bundle metadata, and any catalog facts the Root Catalog README needs; the Publication Interface flattens Bundle Records to `list[Path]` for current callers.
_Avoid_: tuple, path list, manifest blob

**Catalog Manifest**:
The repository-level `manifest.json` that records published agents, hosts, bundle metadata, artifact paths, sizes, checksums, and source recipe pointers. The Host Artifact Publication coordinator writes the Catalog Manifest from Bundle Records.
_Avoid_: host manifest, adapter manifest

**Host Adapter**:
The Host-specific publication implementation used by Host Artifact Publication. One Host Adapter owns compiler invocation, file layout, Generated Agent README content, supporting-file rules, and Bundle Record creation for exactly one Host.
_Avoid_: host branch, special case

**Generated Agent README**:
The README published inside a Host Artifact Bundle, such as `claude-code/<agent>/README.md`, `codex/<agent>/README.md`, or `claude-managed-agents/<agent>/README.md`. It explains installation, requirements, example prompts, and host-specific setup for one installable agent artifact.
_Avoid_: root README, catalog README

**Root Catalog README**:
The repository-level `README.md` generated from catalog state and source-first project rules. It summarizes available agents, hosts, contributor workflow, and repository layout, but it is not the README for one installable agent. Root Catalog README generation stays separate from Host Artifact Publication while consuming the same catalog state produced by the coordinator.
_Avoid_: generated agent README

**Host Artifact Publication**:
The process that turns a Source Recipe into Host Artifact Bundles plus catalog metadata. Host Artifact Publication lives in a dedicated publication package, coordinates one Host Adapter per Host, and keeps `publisher.py` as the Publication Interface compatibility shell; the Root Catalog README is a separate catalog aggregate fed by published bundle metadata.
_Avoid_: copy step, dist sync

**Publication Interface**:
The current caller-facing functions `publish_recipe()` and `publish_recipes()`. The Publication Interface should stay stable while Host Artifact Publication is deepened underneath it.
_Avoid_: new public entrypoint, replacement command

**Publication Migration**:
The incremental refactor path for deepening Host Artifact Publication. Publication Migration introduced the publication package, Bundle Record, coordinator, and Host Adapter seam first, moved the Codex, Claude Code, and Claude Managed Agents Host Adapters, and then moved Catalog Manifest writing into Host Artifact Publication while preserving generated output.
_Avoid_: big-bang rewrite

## Flagged Ambiguities

**README**:
README is ambiguous in this repository. Say **Generated Agent README** for README files inside `claude-code/`, `claude-managed-agents/`, or `codex/`; say **Root Catalog README** for the repository-level catalog document.

## Example Dialogue

Dev: "Should Host Artifact Publication own README generation?"

Domain expert: "Yes, for the Generated Agent README. It is part of the Host Artifact Bundle because the install instructions and host setup rules depend on the Host."

Dev: "Should Host Artifact Publication run compilers, or only consume already-compiled output?"

Domain expert: "It should run the compiler too. Callers should not need to know the ordering from Source Recipe to compiler output to copied Host Artifact Bundle to manifest record."

Dev: "Should Host Artifact Publication be one module with host-specific branches, or use Host Adapters?"

Domain expert: "Use one coordinating module with one Host Adapter per Host. Host-specific file layout, Generated Agent README text, supporting files, and manifest bundle metadata should not leak into the coordinator."

Dev: "Should we change `publish_recipe()` and `publish_recipes()` while deepening Host Artifact Publication?"

Domain expert: "No. Preserve the Publication Interface for now and deepen underneath it so callers and the CLI keep working while the implementation shape changes."

Dev: "Where should the deepened implementation live?"

Domain expert: "Create a dedicated publication package for Host Artifact Publication. Keep `publisher.py` as the compatibility shell for the Publication Interface."

Dev: "Should migration move all Hosts at once?"

Domain expert: "No. Publication Migration should add the package and seam first, then move one Host Adapter at a time with identical generated output."

Dev: "Which Host Adapter moves first?"

Domain expert: "Move Codex first. It is the smallest Host Adapter and proves the seam before edition-heavy Hosts move."

Dev: "What is the current Host Adapter migration state?"

Domain expert: "Codex, Claude Code, and Claude Managed Agents now publish through Host Adapters. Host Artifact Publication owns normal publish and prune-time Catalog Manifest writes. The Publication Interface shell still flattens paths and writes the separate Root Catalog README."

Dev: "Should Host Adapters return paths or richer records?"

Domain expert: "Host Adapters should return Bundle Records internally. The Publication Interface can flatten those records to `list[Path]` for compatibility."

Dev: "Should Host Adapters write manifest entries?"

Domain expert: "No. Host Adapters supply Bundle Records. The Host Artifact Publication coordinator writes the Catalog Manifest so sorting, existing-agent preservation, and pruning stay centralized."

Dev: "What about the root README?"

Domain expert: "That is the Root Catalog README. Keep it as a separate catalog aggregate that consumes the same catalog state produced by the Host Artifact Publication coordinator instead of owning host-specific publication details."
