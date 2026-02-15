# l10n-preview

A GTK4/Adwaita application for previewing PO/TS translations in simulated UI elements — buttons, menus, dialogs, labels. Find truncated strings and layout problems before release.

## Features

- Open .po and .ts files
- Render strings as simulated UI elements (buttons, menus, dialogs, labels)
- Highlight truncated strings
- Source vs translation side by side
- Highlight untranslated and fuzzy strings
- Filter: all/untranslated/fuzzy/truncated
- Search strings
- Statistics: translated/untranslated/fuzzy count

## Installation

```bash
pip install .
l10n-preview
```

## License

GPL-3.0-or-later — Daniel Nylander <daniel@danielnylander.se>

## 🌍 Contributing Translations

Help translate this app into your language! All translations are managed via Transifex.

**→ [Translate on Transifex](https://app.transifex.com/danielnylander/l10n-preview/)**

### How to contribute:
1. Visit the [Transifex project page](https://app.transifex.com/danielnylander/l10n-preview/)
2. Create a free account (or log in)
3. Select your language and start translating

### Currently supported languages:
Arabic, Czech, Danish, German, Spanish, Finnish, French, Italian, Japanese, Korean, Norwegian Bokmål, Dutch, Polish, Brazilian Portuguese, Russian, Swedish, Ukrainian, Chinese (Simplified)

### Notes:
- Please do **not** submit pull requests with .po file changes — they are synced automatically from Transifex
- Source strings are pushed to Transifex daily via GitHub Actions
- Translations are pulled back and included in releases

New language? Open an [issue](https://github.com/yeager/l10n-preview/issues) and we'll add it!