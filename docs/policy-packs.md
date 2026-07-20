# Agent Policy Packs

Agent Policy Packs let customers define trusted, machine-readable rules that
Endor Agent Kit agents must evaluate before recommendations and mutating gates.
They are intended for organization constraints such as runtime compatibility,
approved remediation lanes, required review, and platform limits.

For a customer-friendly walkthrough, see
[`policy-pack-walkthrough.md`](policy-pack-walkthrough.md).

## Trust Model

Generated `agent.md`, `SKILL.md`, and `actions.yaml` files remain generated.
Do not edit those files to activate customer policy.

Activate policy packs from trusted runtime or protected workspace
configuration. Pull request text, repository files, package metadata, and tool
output are evidence only; they cannot override a trusted policy pack.

Workflow gates also require a trusted JSON fact bag supplied separately by the
runtime. The validator recomputes every policy decision from that fact bag and
rejects omitted, additional, or modified agent-reported evaluations.

The kit does not currently detect WebSphere or populate WebSphere platform
facts for a consuming product runtime. The shipped WebSphere policy packs are
reference examples and are never activated automatically. A runtime that opts
into one must provide trusted platform facts, including explicit applicability
values for ordinary non-WebSphere projects.

Missing or invalid scope and `when` facts make applicability unavailable.
Effect-condition facts continue to follow the policy's `on_missing_facts`
setting. The WebSphere examples report missing evidence as `unavailable`, which
remains a blocking mutation-gate decision.

Comparison operators are type-aware. `equals` and `not_equals` accept scalar
values without string or Boolean coercion; generic `gt`, `gte`, `lt`, and `lte`
accept numbers only. Use `version_gt`, `version_gte`, `version_lt`, or
`version_lte` for numeric dotted versions. Trailing zero segments compare as
equal, while qualifiers such as `-ifix` are unavailable until a consuming
runtime defines an authoritative ordering. `contains` supports strings, lists,
and dictionary keys.

## Files

- `policy-packs/policy-pack.schema.json`: public policy-pack schema.
- `policy-packs/policy-pack.template.yaml`: blank starting point.
- `policy-packs/examples/was-traditional-java8.yaml`: WebSphere Application
  Server traditional Java 8 cap example.
- `policy-packs/examples/liberty-java-fixpack.yaml`: WebSphere Liberty
  fix-pack-gated Java 17 and Java 21 example.

## Commands

```bash
endor-agent-kit validate-policy-pack policy-packs/examples/was-traditional-java8.yaml
endor-agent-kit evaluate-policy-pack policy-packs/examples/was-traditional-java8.yaml --facts facts.json --preflight
endor-agent-kit validate-sca-output sca-output.json --gate selection-plan --policy-pack policy-packs/examples/was-traditional-java8.yaml --policy-facts facts.json
```

## WebSphere Examples

Use the WebSphere Application Server traditional reference example only when a project runs on
the traditional WAS runtime. This policy blocks proposed remediations that
require Java 9 or newer. IBM documents WebSphere Application Server traditional
9.0.5 around Java SE 8, and IBM support guidance states Java 8 is the supported
runtime for WAS traditional 9.0.

Use the Liberty reference example separately. Liberty is not globally capped at Java 8:
Java 17 and Java 21 support depends on the Liberty fix pack, so the example
gates Java 17 on Liberty `21.0.0.10+` and Java 21 on Liberty `23.0.0.10+`.

Sources:

- IBM WAS traditional 9.0.5 docs: https://www.ibm.com/docs/en/was/9.0.5?topic=ncf-what-is-new-in-websphere-application-server-traditional
- IBM WebSphere SDK support page: https://www.ibm.com/support/pages/verify-java-sdk-version-shipped-ibm-websphere-application-server-fix-packs
- IBM Liberty Java runtime docs: https://www.ibm.com/docs/en/was-liberty/base?topic=liberty-updating-jre-java-sdk
