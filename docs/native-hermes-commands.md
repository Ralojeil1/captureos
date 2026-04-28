# Native Hermes Command Notes

CaptureOS works as a skill pack first. In many setups, loading the skills is enough:

```text
/skill captureos
/capture
/normal
```

Some messaging gateways expose only registered native slash commands in their command menus. If your gateway does not show `/capture` and `/normal`, you have three options:

1. Use explicit skill loading and type the commands manually.
2. Add `/capture` and `/normal` to your own custom command registry.
3. Build or install a small Hermes plugin that maps those slash commands to the `capture` and `normal` skills.

Expected native behavior:

- `/capture` dispatches the `capture` skill.
- `/normal` dispatches the `normal` skill.
- No short aliases are required.

This repository does not ship environment-specific patches from a private Hermes checkout. Keep native gateway integration generic and reviewable before publishing it as code.
