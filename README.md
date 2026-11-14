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

GitHub Actions deploys the site over SSH when the latest commit pushed to `main`
contains `[deploy]`. To deploy manually, run **Deploy static site** from the
Actions tab on `main` and enter `DEPLOY`.

The workflow stages and verifies the site before atomically replacing the live
directory. It retains the previous site for rollback; rollback is manual if
public verification fails. Recognized backups are cleaned up after at least an
hour. See `.github/workflows/deploy.yml` for configuration and included files.
