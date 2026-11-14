# Navikarana Labs

Independent research and engineering. Live at https://navikarana.io.

### Local Preview

Plain HTML and CSS with a small Contact-page copy script. No dependencies or build step.

```sh
python3 preview.py
```

Then open http://localhost:8000.

Third-party assets (fonts, icons) and their licenses are listed in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

### Deployment

`.github/workflows/deploy.yml` deploys the static site over SSH; the server
does not need access to GitHub. A push to `main` deploys when the **latest**
commit message contains `[deploy]`. Alternatively, dispatch the workflow on
`main` and enter `DEPLOY` as the confirmation. Deployments and daily cleanup
share a concurrency group; rapid pushes can replace pending runs, so not every
intermediate commit is guaranteed a separate deployment.

The workflow packages an explicit allowlist (`.htaccess`, root HTML, CSS and
favicon, and the `about/`, `contact/`, `projects/`, and `public/` directories).
Update the allowlist if new public files are added. It creates a commit/run
version file and a SHA-256 manifest, uploads and verifies a sibling staging
directory, then atomically exchanges it with the document root. It checks
`https://navikarana.io/deployment-version.json` for the expected version.
There is no deployment-status file or updating indicator.

Before configuring or triggering the first deployment:

1. Confirm the document root is a real directory, not a symlink, and inventory
   its contents. Preserve any server-managed files, uploads, certificates, or
   application data: the workflow replaces the **entire** directory. Disable
   any competing Git auto-deployment. Keep the original site for rollback.
2. Confirm SSH access, enough space for both sites, and server-side Python 3,
   tar and `sha256sum`. The host must run Linux and support
   `renameat2(RENAME_EXCHANGE)` on the document-root filesystem, with permission
   to create sibling directories. Each deployment tests this in an isolated
   temporary sibling before uploading or touching the live directory.
3. Configure these GitHub repository secrets:
   - `DEPLOY_HOST`, `DEPLOY_PORT`, `DEPLOY_USER`: SSH connection details.
   - `DEPLOY_WEB_ROOT`: absolute path to the live document-root directory,
     without a trailing slash. Paths must use letters, numbers, `_`, `-`, `.`,
     and `/`, and cannot contain `..`.
   - `DEPLOY_SSH_KEY`: dedicated private SSH key. Do not commit or share it.
   - `DEPLOY_KNOWN_HOSTS`: server host-key entry, independently verified against
     a trusted fingerprint. Use `[host]:port` syntax for a non-default port.

Strict host-key checking is enabled. A site-restricted deployment account is
preferable. Test the isolated exchange independently before the first live run,
for example by passing `scripts/check-exchange.py` to `python3 -` over SSH with
the document-root path as its argument. Check that the public version URL is
reachable and not overridden by a cache, proxy, or host configuration.

The previous site stays in the sibling `.navikarana-release-<run>-<attempt>`
directory. A failed public verification reports failure and retains that
directory; it does **not** automatically roll back. After successful public
verification, only recognized managed backups are marked for cleanup. A daily
scheduled job removes marked backups no sooner than one hour later, and skips
unknown, modified, symlinked, or Git checkout directories. The original site
and failed staging uploads are not automatically removed. Scheduled runs may
be delayed. Retaining old assets in a backup does not make them publicly
available to pages opened before an exchange.

Run the local deployment safeguards tests with:

```sh
python3 -m unittest discover -s tests -v
```
