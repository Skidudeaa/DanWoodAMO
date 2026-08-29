# Vendored: dark-roast-theme

Generated build artifacts copied verbatim from
[`Skidudeaa/dark-roast-theme`](https://github.com/Skidudeaa/dark-roast-theme)
at `dist/css/`. **Do not hand-edit these files.**

They are the scoped variants, each defining its `--dr-*` tokens under a
`[data-theme="..."]` selector, so all five can coexist in one document and be
switched at runtime.

| File | `data-theme` |
|---|---|
| `dark-roast-scoped.css` | `dark-roast` (Black Label) |
| `dark-roast-house-blend-scoped.css` | `dark-roast-house-blend` |
| `dark-roast-copper-roast-scoped.css` | `dark-roast-copper-roast` |
| `dark-roast-blue-mountain-scoped.css` | `dark-roast-blue-mountain` |
| `dark-roast-cold-brew-scoped.css` | `dark-roast-cold-brew` |

## Updating

Rebuild in the theme repo and re-copy:

```sh
cd path/to/dark-roast-theme
npm run build
cp dist/css/dark-roast-scoped.css \
   dist/css/dark-roast-house-blend-scoped.css \
   dist/css/dark-roast-copper-roast-scoped.css \
   dist/css/dark-roast-blue-mountain-scoped.css \
   dist/css/dark-roast-cold-brew-scoped.css \
   path/to/DanWoodAMO/frontend/vendor/dark-roast/
```

After updating, confirm every token the identity layer references still resolves
in all five variants:

```sh
cd frontend
grep -oE 'var\(--dr-[a-z0-9-]+' dialectic.css | sed 's/var(//' | sort -u > /tmp/used.txt
for f in vendor/dark-roast/*.css; do
  grep -oE '^\s*--dr-[a-z0-9-]+:' "$f" | tr -d ' :' | sort -u > /tmp/have.txt
  echo "$(basename "$f"): $(comm -23 /tmp/used.txt /tmp/have.txt | tr '\n' ' ')"
done
```

Any token printed after a filename is referenced but undefined in that variant and
needs either a fallback in `dialectic.css` or a fix upstream. `--dr-structural`
is expected to be missing from `dark-roast-scoped.css`; the identity layer already
supplies a fallback for it.

`LICENSE` is the upstream license, retained as required.
