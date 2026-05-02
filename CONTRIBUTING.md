# Contributing

Contributions are welcome — bug fixes, new features, documentation improvements, or entirely new tools that fit the project's scope.

## Getting Started

1. **Fork** the repository and clone your fork.
2. **Create a branch** from `main` for your work:
   ```bash
   git checkout -b feat/your-feature-name
   ```
3. **Make your changes.** Each project lives in its own directory — keep changes scoped to the relevant folder.
4. **Test your work** before submitting. If the project has a Docker setup, verify it builds and runs.
5. **Commit** with clear, descriptive messages:
   ```
   fliphtml5-liberator: handle WASM modules with stripped exports
   ```
6. **Push** your branch and open a **Pull Request** against `main`.

## Guidelines

- **One PR per concern.** Don't bundle unrelated changes.
- **Follow existing patterns.** Match the code style, directory layout, and documentation conventions already in use.
- **Document what you change.** Update the relevant project README if your change affects usage, configuration, or dependencies.
- **Keep it self-contained.** Each project folder should remain independently usable.

## Commit Message Format

Use the pattern: `<project>: <short description>`

```
cyberdrop-dl-gui: add batch URL import from clipboard
ha-connect-portable: fix ZBT-2 baud rate detection on macOS
fliphtml5-liberator: skip pages with empty image refs
```

For repo-level changes (README, CI, community files): `repo: <description>`

## Reporting Bugs

Open an [issue](https://github.com/silenthooligan/code-sharing/issues) with:
- Which project is affected.
- Steps to reproduce.
- Expected vs. actual behavior.
- Environment details (OS, Python version, Docker version, etc.).

## Suggesting Features

Open an issue with the `enhancement` label. Describe the use case, not just the solution — the "why" matters more than the "how."

## License

By contributing, you agree that your work will be licensed under the project's [MIT License](./LICENSE).
