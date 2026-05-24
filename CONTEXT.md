# Endor Labs Agent Kit Context

Endor Labs Agent Kit is a source-first catalog for portable Endor workflow agents. This context records the project language used when discussing recipe authoring, host publication, generated artifacts, and installable catalog outputs.

## Language

**Source Recipe**:
The maintainer-authored definition for one agent under `source/agents/<agent>/recipe.yaml`, together with its nearby source files such as instructions, eval cases, actions, and architecture diagram. One Source Recipe can publish zero or more Host Artifact Bundles.
_Avoid_: generated recipe, catalog recipe

**Prepared Source Recipe**:
The validated, loaded Source Recipe plus the render inputs and source paths needed by compilers and Host Adapters: recipe object, instructions, action contracts, architecture path, and action-contract path. Publication prepares each Source Recipe once and passes the Prepared Source Recipe through compiler and Host Adapter work instead of letting each layer reload from disk.
_Avoid_: recipe tuple, compiler reload state

**Compiler Rendering**:
The host-independent prompt rendering rules shared by Host compilers, including edition selection, instruction section extraction, action-contract text, and frontmatter indentation. Compiler Rendering is not owned by the Claude Code compiler; Host compilers add host-specific artifact shape, frontmatter/YAML, tool restrictions, and setup text around the shared rendered prompt.
_Avoid_: Claude helper, prompt util

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

**Catalog Manifest Schema Record**:
The typed in-code representation of Catalog Manifest agents, Host Artifact Bundles, artifact checksums, and source recipe pointers. Host Artifact Publication writes Catalog Manifest Schema Records and Catalog Manifest Lookup reads the same records, converting to or from JSON only at the Catalog Manifest boundary.
_Avoid_: publication manifest dict, read-side duplicate model

**Catalog Manifest Lookup**:
The read-side module that loads the Catalog Manifest and returns Host Artifact Bundle records plus artifact checksums for install drift checks and future install surfaces. Callers ask Catalog Manifest Lookup for bundle and artifact records instead of reconstructing generated catalog paths.
_Avoid_: path probe, source file scan

**Source Recipe Safety Posture**:
The derived safety and transport view of a Source Recipe, including whether it uses MCP, uses documented `endorctl api` invocations, can run commands, can read or write files, can open change requests, and needs Endor setup guidance. Compilers and Host Adapters consume Source Recipe Safety Posture instead of recomputing those facts from raw recipe fields.
_Avoid_: compiler safety helper, host policy blob

**Host Adapter**:
The Host-specific publication implementation used by Host Artifact Publication. One Host Adapter owns compiler invocation, file layout, Generated Agent README content, supporting-file rules, and Bundle Record creation for exactly one Host.
_Avoid_: host branch, special case

**Generated Agent README**:
The README published inside a Host Artifact Bundle, such as `claude-code/<agent>/README.md`, `codex/<agent>/README.md`, or `claude-managed-agents/<agent>/README.md`. It explains installation, requirements, example prompts, and host-specific setup for one installable agent artifact.
_Avoid_: root README, catalog README

**Root Catalog README**:
The repository-level `README.md` generated from catalog state and source-first project rules. It summarizes available agents, hosts, contributor workflow, and repository layout, but it is not the README for one installable agent. Root Catalog README generation stays separate from Host Artifact Publication while consuming the same catalog state produced by the coordinator.
_Avoid_: generated agent README

**Catalog Aggregate**:
A repository-level catalog view rendered from Catalog Manifest state after Host Artifact Publication has produced Host Artifact Bundles. The Root Catalog README is the first Catalog Aggregate. Catalog Aggregates stay separate from Host Adapters because they summarize across Hosts instead of publishing one Host Artifact Bundle.
_Avoid_: host readme, manifest writer

**Primary Installed Artifact**:
The single installed file that `check-install` compares for current CLI compatibility, such as `.claude/agents/<agent>.md` for Claude Code or `skills/<agent>/SKILL.md` for Codex. A Primary Installed Artifact is a compatibility view of a fuller Host Artifact Bundle, not the whole install surface.
_Avoid_: whole bundle check, source artifact

**Host Artifact Publication**:
The process that turns a Source Recipe into Host Artifact Bundles plus catalog metadata. Host Artifact Publication lives in a dedicated publication package, coordinates one Host Adapter per Host, and keeps `publisher.py` as the Publication Interface compatibility shell; the Root Catalog README is a separate catalog aggregate fed by published bundle metadata.
_Avoid_: copy step, dist sync

**Workflow Gate**:
A named checkpoint in a generated agent workflow, such as AI SAST triage, AI SAST remediation, AI SAST exception policy, SCA Selection / Plan, SCA apply, SCA validation, or SCA PR/MR publication. Each Workflow Gate owns the structured output requirements and rendered artifact checks needed before that workflow can advance.
_Avoid_: phase string, mode flag

**Workflow Output Contract**:
The mechanical validation, rendering, and linting rules for one Endor workflow agent's output at a Workflow Gate. Workflow Output Contracts live behind gate-local modules so CLI commands and tests exercise the same gate Interface instead of reconstructing JSON and PR/MR body rules directly.
_Avoid_: output helper, validation util

**Publication Interface**:
The current caller-facing functions `publish_recipe()` and `publish_recipes()`. The Publication Interface should stay stable while Host Artifact Publication is deepened underneath it.
_Avoid_: new public entrypoint, replacement command

**Publication Migration**:
The incremental refactor path for deepening Host Artifact Publication. Publication Migration introduced the publication package, Bundle Record, coordinator, and Host Adapter seam first, moved the Codex, Claude Code, and Claude Managed Agents Host Adapters, moved Catalog Manifest writing into Host Artifact Publication, and moved Root Catalog README generation into a Catalog Aggregate while preserving generated output.
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

Domain expert: "Codex, Claude Code, and Claude Managed Agents now publish through Host Adapters. Host Artifact Publication owns normal publish and prune-time Catalog Manifest writes. A Catalog Aggregate owns Root Catalog README generation. The Publication Interface shell flattens paths and coordinates those deeper modules."

Dev: "Should Host Adapters return paths or richer records?"

Domain expert: "Host Adapters should return Bundle Records internally. The Publication Interface can flatten those records to `list[Path]` for compatibility."

Dev: "Should Host Adapters write manifest entries?"

Domain expert: "No. Host Adapters supply Bundle Records. The Host Artifact Publication coordinator writes the Catalog Manifest so sorting, existing-agent preservation, and pruning stay centralized."

Dev: "What about the root README?"

Domain expert: "That is the Root Catalog README. Keep it as a separate catalog aggregate that consumes the same catalog state produced by the Host Artifact Publication coordinator instead of owning host-specific publication details."

Dev: "Should install drift checks read generated catalog files directly?"

Domain expert: "No. Use Catalog Manifest Lookup as the install drift interface. Keep current `check-install` compatibility focused on the Primary Installed Artifact, but let the lookup module return the full Host Artifact Bundle record so plugin and managed-agent installs can deepen later."

Dev: "Should Host Adapters decide from raw recipe fields whether an artifact uses MCP or endorctl?"

Domain expert: "No. They should consume Source Recipe Safety Posture and keep only Host-specific wording, tools, setup-file placement, and artifact layout local."

Dev: "Should publication and install drift lookup keep separate manifest record shapes?"

Domain expert: "No. Use Catalog Manifest Schema Records for both write-side publication and read-side Catalog Manifest Lookup so future bundle fields only need one schema change."

Dev: "Should every Host Adapter and compiler reload the recipe from disk?"

Domain expert: "No. Publication should create a Prepared Source Recipe once, then pass it through compiler rendering, Host Artifact Publication, and Catalog Aggregate work."

Dev: "Should the AI SAST and SCA output validators stay as broad workflow modules?"

Domain expert: "No. Keep compatibility wrappers for existing imports and CLI commands, but organize Workflow Output Contracts by Workflow Gate so remediation, exception policy, PR/MR, and validation rules each have local ownership."

Dev: "Should Codex, Raw, and Claude Managed Agents import private prompt helpers from the Claude Code compiler?"

Domain expert: "No. Put host-independent prompt rendering in Compiler Rendering, and leave Host compilers to own only Host-specific artifact shape, permissions, and setup text."
