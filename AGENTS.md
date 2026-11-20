# Contributor / coding-agent guidance

- Treat this GitHub repository, its open Issues, PRs, and current code as the source of truth; chat history is not authoritative.
- Scope includes Telegram **Custom Emoji** now and **Stickers** later. Future Stickers are a direction, not authorization to publish/deploy.
- Before changing an upstream asset, verify its specific license, copyright notice and attribution obligations in `docs/ICON-SOURCES.md`.
- Keep imports, rendering, previews, and irreversible Telegram publication as distinct steps. Live publication requires explicit current owner approval for the exact set/target.
- Never commit Telegram bot tokens, service credential IDs, private message contents, user IDs, local selection JSON, imported media whose rights have not been verified, or virtualenv files.
- Preserve existing testable behavior; update a meaningful targeted unit test when behavior changes. Distinguish offline fake-API tests from live Telegram acceptance.
- Avoid new dependencies, fixed limits and process overhead without evidence of actual need; actual upstream Telegram API limits are valid.
- Use PR/independent review for meaningful subsequent code changes and request release/integration authorization where required by owner policy.
- Keep durable project scope in `docs/PROJECT-SPEC.md`, source choices in `docs/ICON-SOURCES.md`, and active dependencies in GitHub Issues.
