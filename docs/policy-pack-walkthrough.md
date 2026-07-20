# Agent Policy Packs Test Drive

Hey, here's how you can test out this new feature. Here's an example. Give it a shot.

Agent Policy Packs let you define customer-owned YAML rules that Endor Agent Kit agents must evaluate before recommendations advance into changes. The important behavior to test is:

- A policy pack validates before use.
- A fact bag evaluates deterministically to `passed`, `blocked`, `warned`, `requires_review`, or `unavailable`.
- Workflow gates recompute policy decisions from a separately trusted fact bag.
- Mutating workflow gates reject blocked, omitted, additional, or modified policy decisions.

Policy packs are trusted runtime or workspace configuration. They are not meant to be edited inside generated `agent.md`, `SKILL.md`, or `actions.yaml` files.

The shipped WebSphere packs are reference examples. They are not activated
automatically, and the kit does not populate WebSphere platform facts for a
consuming runtime. Before activation, use `--preflight` so missing scope or
applicability facts fail clearly instead of being mistaken for a policy match.

## Quick Test

From the `endor-labs-agent-kit` repository:

```bash
PYTHONPATH=src python3 -m endor_agent_kit.cli validate-policy-pack \
  policy-packs/examples/was-traditional-java8.yaml
```

Expected result:

```text
OK: policy-packs/examples/was-traditional-java8.yaml
```

Now evaluate the shipped WebSphere traditional policy with a proposed Java 17 remediation:

```bash
cat > /tmp/was-traditional-java17-facts.json <<'JSON'
{
  "agent": { "id": "sca-remediation" },
  "ecosystem": "maven",
  "platform": {
    "websphere": {
      "present": true,
      "family": "traditional",
      "version": "9.0.5",
      "source": "trusted runtime config"
    }
  },
  "proposed": {
    "runtime": { "java": { "major": 17 } },
    "package": "org.springframework.boot:spring-boot-starter-web",
    "to_version": "3.x"
  }
}
JSON

PYTHONPATH=src python3 -m endor_agent_kit.cli evaluate-policy-pack \
  policy-packs/examples/was-traditional-java8.yaml \
  --facts /tmp/was-traditional-java17-facts.json \
  --preflight
```

Expected decision:

```json
"decision": "blocked"
```

Control test:

```bash
python3 - <<'PY'
import json
from pathlib import Path

facts = json.loads(Path("/tmp/was-traditional-java17-facts.json").read_text())
facts["proposed"]["runtime"]["java"]["major"] = 8
Path("/tmp/was-traditional-java8-facts.json").write_text(json.dumps(facts, indent=2))
PY

PYTHONPATH=src python3 -m endor_agent_kit.cli evaluate-policy-pack \
  policy-packs/examples/was-traditional-java8.yaml \
  --facts /tmp/was-traditional-java8-facts.json
```

Expected decision:

```json
"decision": "passed"
```

## Try Your Own Rule

Here is a simple custom policy for Java 8 applications:

```yaml
policy_pack_version: 1
id: java-runtime-compatibility
version: 2026.07.02

policies:
  - id: java8-app-no-java9-plus-remediation
    title: Java 8 applications cannot accept remediations requiring Java 9 or newer
    effect: deny
    applies_to:
      agents: ["sca-remediation", "upgrade-impact-analysis"]
      ecosystems: ["maven"]
    when:
      fact: current.runtime.java.major
      equals: 8
    deny_if:
      fact: proposed.runtime.java.major
      gt: 8
    on_missing_facts: deny
    message: "Do not recommend or apply a remediation requiring Java 9+ for applications pinned to Java 8."
```

Save it as `/tmp/java8-policy.yaml`, then run:

```bash
PYTHONPATH=src python3 -m endor_agent_kit.cli validate-policy-pack /tmp/java8-policy.yaml
```

Save a trusted fact bag as `/tmp/java8-policy-facts.json`:

```json
{
  "agent": { "id": "sca-remediation" },
  "ecosystem": "maven",
  "repo": {
    "path": "/path/to/your/repo",
    "build_system": "maven"
  },
  "current": {
    "runtime": {
      "java": {
        "major": 8,
        "source": "pom.xml <java.version>1.8</java.version>"
      }
    }
  },
  "proposed": {
    "runtime": { "java": { "major": 17 } },
    "package": "example:dependency",
    "to_version": "example-release"
  }
}
```

```bash
PYTHONPATH=src python3 -m endor_agent_kit.cli evaluate-policy-pack \
  /tmp/java8-policy.yaml \
  --facts /tmp/java8-policy-facts.json
```

Expected decision:

```json
"decision": "blocked"
```

Change `proposed.runtime.java.major` to `8` and evaluate again. Expected decision:

```json
"decision": "passed"
```

## Test A Workflow Gate

For SCA remediation, the apply/validate/PR gates can enforce policy output:

```bash
PYTHONPATH=src python3 -m endor_agent_kit.cli validate-sca-output \
  /tmp/sca-agent-output.json \
  --gate apply \
  --policy-pack /tmp/java8-policy.yaml \
  --policy-facts /tmp/java8-policy-facts.json
```

The caller must source `--policy-facts` from trusted runtime or protected
workspace configuration. Do not build this fact bag from model-authored output.

If `/tmp/sca-agent-output.json` contains a blocked policy decision and an approved remediation, the validator should reject it with messages like:

```text
ERROR: policy_evaluations: blocking policy decision cannot accompany approved risk_decision
ERROR: policy_evaluations[0].decision: blocked blocks mutation gate
```

That is the product guarantee to look for: the model can draft a plan, but the
validator independently recomputes policy decisions and prevents blocked or
modified policy evidence from advancing into mutation.

## What To Send Back

If you try this against your own rules, please send:

- The policy pack YAML.
- The fact bag JSON.
- The `evaluate-policy-pack` output.
- The agent output JSON if you tested a workflow validator.
- Whether the result matched the business rule you expected.

Do not include API keys, credentials, tokens, or private secret values.
