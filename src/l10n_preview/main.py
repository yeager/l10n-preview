"""L10n Preview — GTK4/Adwaita application for previewing PO/TS translations."""

import csv
import os
import sys
import gettext
import json
import locale
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Pango, Gdk  # noqa: E402

from .po_parser import parse_file, TranslationEntry, EntryState  # noqa: E402
from datetime import datetime as _dt_now

# i18n setup
APP_ID = "se.danielnylander.l10n-preview"
LOCALE_DIR = str(Path(__file__).parent.parent.parent / "po")
if not os.path.isdir(LOCALE_DIR):
    LOCALE_DIR = "/usr/share/locale"

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass

gettext.bindtextdomain("l10n-preview", LOCALE_DIR)
gettext.textdomain("l10n-preview")
_ = gettext.gettext

class PreviewRow(Gtk.Box):
    """A row showing source vs translation with simulated UI element."""

    def __init__(self, entry: TranslationEntry):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.entry = entry
        self.add_css_class("card")
        self.set_margin_start(6)
        self.set_margin_end(6)
        self.set_margin_top(3)
        self.set_margin_bottom(3)

        # Header: state badge + UI hint + reference
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_start(8)
        header.set_margin_end(8)
        header.set_margin_top(6)

        # State badge
        badge = Gtk.Label()
        if entry.state == EntryState.TRANSLATED:
            badge.set_label("✓")
            badge.add_css_class("success")
        elif entry.state == EntryState.FUZZY:
            badge.set_label("~")
            badge.add_css_class("warning")
        else:
            badge.set_label("✗")
            badge.add_css_class("error")
        badge.add_css_class("caption")
        header.append(badge)

        # UI hint
        hint_label = Gtk.Label(label=entry.ui_hint.upper())
        hint_label.add_css_class("caption")
        hint_label.add_css_class("dim-label")
        header.append(hint_label)

        if entry.is_truncated:
            trunc = Gtk.Label(label=_("TRUNCATED"))
            trunc.add_css_class("caption")
            trunc.add_css_class("error")
            header.append(trunc)

        if entry.reference:
            ref = Gtk.Label(label=entry.reference)
            ref.add_css_class("caption")
            ref.add_css_class("dim-label")
            ref.set_hexpand(True)
            ref.set_halign(Gtk.Align.END)
            ref.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            header.append(ref)

        self.append(header)

        # Source vs Translation side by side
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content.set_margin_start(8)
        content.set_margin_end(8)
        content.set_margin_bottom(6)
        content.set_homogeneous(True)

        # Source
        src_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        src_title = Gtk.Label(label=_("Source"))
        src_title.add_css_class("caption")
        src_title.add_css_class("dim-label")
        src_title.set_halign(Gtk.Align.START)
        src_box.append(src_title)

        src_label = Gtk.Label(label=entry.msgid)
        src_label.set_wrap(True)
        src_label.set_halign(Gtk.Align.START)
        src_label.set_selectable(True)
        src_box.append(src_label)
        content.append(src_box)

        # Translation / simulated UI element
        trans_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        trans_title = Gtk.Label(label=_("Translation"))
        trans_title.add_css_class("caption")
        trans_title.add_css_class("dim-label")
        trans_title.set_halign(Gtk.Align.START)
        trans_box.append(trans_title)

        sim = self._build_simulated(entry)
        trans_box.append(sim)
        content.append(trans_box)

        self.append(content)

    def _build_simulated(self, entry: TranslationEntry) -> Gtk.Widget:
        """Build a simulated UI element based on the hint."""
        text = entry.msgstr or entry.msgid
        if not text:
            text = "—"

        if entry.ui_hint == "button":
            btn = Gtk.Button(label=text)
            btn.set_sensitive(False)
            if entry.is_truncated:
                btn.add_css_class("destructive-action")
            return btn

        elif entry.ui_hint == "menu":
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            box.add_css_class("toolbar")
            lbl = Gtk.Label(label=text)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            if entry.is_truncated:
                lbl.add_css_class("error")
            box.append(lbl)
            return box

        elif entry.ui_hint == "dialog":
            frame = Gtk.Frame()
            lbl = Gtk.Label(label=text)
            lbl.set_wrap(True)
            lbl.set_margin_start(8)
            lbl.set_margin_end(8)
            lbl.set_margin_top(4)
            lbl.set_margin_bottom(4)
            frame.set_child(lbl)
            return frame

        else:  # label, tooltip, etc
            lbl = Gtk.Label(label=text)
            lbl.set_wrap(True)
            lbl.set_halign(Gtk.Align.START)
            lbl.set_selectable(True)
            if entry.is_truncated:
                lbl.add_css_class("error")
            if entry.state == EntryState.UNTRANSLATED:
                lbl.add_css_class("dim-label")
            return lbl

class L10nPreviewWindow(Adw.ApplicationWindow):
    """Main application window."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.entries: list[TranslationEntry] = []
        self.filtered_entries: list[TranslationEntry] = []
        self.current_filter = "all"
        self.search_text = ""

        self.set_default_size(900, 700)
        self.set_title(_("L10n Preview"))

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar
        header = Adw.HeaderBar()
        self.set_title(_("L10n Preview"))

        # Open button
        open_btn = Gtk.Button(icon_name="document-open-symbolic")
        open_btn.set_tooltip_text(_("Open PO/TS file"))
        open_btn.connect("clicked", self._on_open)
        header.pack_start(open_btn)

        # Menu button
        menu = Gio.Menu.new()
        menu.append(_("About L10n Preview"), "app.about")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        header.pack_end(menu_btn)

        # Theme toggle
        self._theme_btn = Gtk.Button(icon_name="weather-clear-night-symbolic",
                                     tooltip_text="Toggle dark/light theme")
        self._theme_btn.connect("clicked", self._on_theme_toggle)
        header.pack_end(self._theme_btn)

        # Search toggle
        self.search_btn = Gtk.ToggleButton(icon_name="system-search-symbolic")
        self.search_btn.set_tooltip_text(_("Search"))
        self.search_btn.connect("toggled", self._on_search_toggled)
        # Export button
        export_btn = Gtk.Button(icon_name="document-save-symbolic",
                                tooltip_text=_("Export data"))
        export_btn.connect("clicked", self._on_export_clicked)
        header.pack_end(export_btn)

        header.pack_end(self.search_btn)

        main_box.append(header)

        # Search bar
        self.search_bar = Gtk.SearchBar()
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_bar.set_child(self.search_entry)
        self.search_bar.connect_entry(self.search_entry)
        main_box.append(self.search_bar)

        # Stats bar
        self.stats_label = Gtk.Label(label=_("No file loaded"))
        self.stats_label.add_css_class("caption")
        self.stats_label.set_margin_start(12)
        self.stats_label.set_margin_top(4)
        self.stats_label.set_margin_bottom(4)
        self.stats_label.set_halign(Gtk.Align.START)
        main_box.append(self.stats_label)

        # Filter bar
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        filter_box.set_margin_start(12)
        filter_box.set_margin_end(12)
        filter_box.set_margin_bottom(4)

        filters = [
            ("all", _("All")),
            ("untranslated", _("Untranslated")),
            ("fuzzy", _("Fuzzy")),
            ("truncated", _("Truncated")),
        ]

        self.filter_buttons = {}
        for fid, flabel in filters:
            btn = Gtk.ToggleButton(label=flabel)
            btn.connect("toggled", self._on_filter, fid)
            filter_box.append(btn)
            self.filter_buttons[fid] = btn

        self.filter_buttons["all"].set_active(True)
        main_box.append(filter_box)

        # Separator
        main_box.append(Gtk.Separator())

        # Scrollable list
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.list_box.set_margin_top(4)
        self.list_box.set_margin_bottom(4)

        scroll.set_child(self.list_box)
        main_box.append(scroll)

        # Drag and drop
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self.add_controller(drop_target)

        # Status bar
        self._status_bar = Gtk.Label(label="", halign=Gtk.Align.START,
                                     margin_start=12, margin_end=12, margin_bottom=4)
        self._status_bar.add_css_class("dim-label")
        self._status_bar.add_css_class("caption")
        main_box.append(self._status_bar)

        self.set_content(main_box)

    def _on_export_clicked(self, *_args):
        dialog = Adw.MessageDialog(transient_for=self,
                                   heading=_("Export Data"),
                                   body=_("Choose export format:"))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("csv", "CSV")
        dialog.add_response("json", "JSON")
        dialog.set_response_appearance("csv", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_export_format_chosen)
        dialog.present()

    def _on_export_format_chosen(self, dialog, response):
        if response not in ("csv", "json"):
            return
        self._export_fmt = response
        fd = Gtk.FileDialog()
        fd.set_initial_name(f"l10n-preview.{response}")
        fd.save(self, None, self._on_export_save)

    def _on_export_save(self, dialog, result):
        try:
            path = dialog.save_finish(result).get_path()
        except Exception:
            return
        data = [{"msgid": e.msgid, "msgstr": e.msgstr, "state": e.state.name,
                 "context": e.context, "reference": e.reference, "comment": e.comment}
                for e in self.entries]
        if not data:
            return
        if self._export_fmt == "csv":
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=data[0].keys())
                w.writeheader()
                w.writerows(data)
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def _on_open(self, _btn):
        dialog = Gtk.FileDialog()
        ff = Gtk.FileFilter()
        ff.set_name(_("Translation files (*.po, *.ts)"))
        ff.add_pattern("*.po")
        ff.add_pattern("*.pot")
        ff.add_pattern("*.ts")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(ff)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_file_opened)

    def _on_file_opened(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            if f:
                self._load_file(f.get_path())
        except GLib.Error:
            pass

    def _on_drop(self, _target, value, _x, _y):
        if isinstance(value, Gio.File):
            self._load_file(value.get_path())
            return True
        return False

    def _load_file(self, path: str):
        try:
            self.entries = parse_file(path)
        except Exception as e:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=_("Error"),
                body=str(e),
            )
            dialog.add_response("ok", _("OK"))
            dialog.present()
            return

        self.set_title(f"{Path(path).name} — {_('L10n Preview')}")
        self._update_stats()
        self._apply_filter()

    def _update_stats(self):
        total = len(self.entries)
        translated = sum(1 for e in self.entries if e.state == EntryState.TRANSLATED)
        untranslated = sum(1 for e in self.entries if e.state == EntryState.UNTRANSLATED)
        fuzzy = sum(1 for e in self.entries if e.state == EntryState.FUZZY)
        truncated = sum(1 for e in self.entries if e.is_truncated)

        self.stats_label.set_label(
            _("Total: {total} | Translated: {translated} | Untranslated: {untranslated} | Fuzzy: {fuzzy} | Truncated: {truncated}").format(
                total=total, translated=translated, untranslated=untranslated,
                fuzzy=fuzzy, truncated=truncated
            )
        )

    def _on_filter(self, btn, fid):
        if btn.get_active():
            self.current_filter = fid
            for k, b in self.filter_buttons.items():
                if k != fid:
                    b.set_active(False)
            self._apply_filter()
        elif all(not b.get_active() for b in self.filter_buttons.values()):
            self.filter_buttons["all"].set_active(True)

    def _on_search_toggled(self, btn):
        self.search_bar.set_search_mode(btn.get_active())

    def _on_search_changed(self, entry):
        self.search_text = entry.get_text().lower()
        self._apply_filter()

    def _apply_filter(self):
        if not hasattr(self, 'list_box'):
            return
        # Clear list
        child = self.list_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.list_box.remove(child)
            child = next_child

        for entry in self.entries:
            # Filter by state
            if self.current_filter == "untranslated" and entry.state != EntryState.UNTRANSLATED:
                continue
            if self.current_filter == "fuzzy" and entry.state != EntryState.FUZZY:
                continue
            if self.current_filter == "truncated" and not entry.is_truncated:
                continue

            # Filter by search
            if self.search_text:
                haystack = (entry.msgid + entry.msgstr + entry.context + entry.comment).lower()
                if self.search_text not in haystack:
                    continue

            self.list_box.append(PreviewRow(entry))

        # Count shown
        shown = 0
        child = self.list_box.get_first_child()
        while child:
            shown += 1
            child = child.get_next_sibling()

        if not self.entries:
            placeholder = Gtk.Label(label=_("Drag and drop a .po or .ts file to preview"))
            placeholder.add_css_class("dim-label")
            placeholder.set_margin_top(48)
            self.list_box.append(placeholder)

    def _on_theme_toggle(self, _btn):
        sm = Adw.StyleManager.get_default()
        if sm.get_color_scheme() == Adw.ColorScheme.FORCE_DARK:
            sm.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            self._theme_btn.set_icon_name("weather-clear-night-symbolic")
        else:
            sm.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            self._theme_btn.set_icon_name("weather-clear-symbolic")

    def _update_status_bar(self):
        self._status_bar.set_text("Last updated: " + _dt_now.now().strftime("%Y-%m-%d %H:%M"))

class L10nPreviewApp(Adw.Application):
    """Main application class."""

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.refresh", ["F5"])
        self.set_accels_for_action("app.shortcuts", ["<Control>slash"])
        self.set_accels_for_action("app.export", ["<Control>e"])
        for n, cb in [("quit", lambda *_: self.quit()),
                      ("refresh", lambda *_: self._do_refresh()),
                      ("shortcuts", self._show_shortcuts_window),
                      ("export", lambda *_: self.get_active_window() and self.get_active_window()._on_export_clicked())]:
            a = Gio.SimpleAction.new(n, None); a.connect("activate", cb); self.add_action(a)

    def _do_refresh(self):
        w = self.get_active_window()
        if w and hasattr(w, '_load_file'): w._load_file(None)

    def _show_shortcuts_window(self, *_args):
        win = Gtk.ShortcutsWindow(transient_for=self.get_active_window(), modal=True)
        section = Gtk.ShortcutsSection(visible=True, max_height=10)
        group = Gtk.ShortcutsGroup(visible=True, title="General")
        for accel, title in [("<Control>q", "Quit"), ("F5", "Refresh"), ("<Control>slash", "Keyboard shortcuts")]:
            s = Gtk.ShortcutsShortcut(visible=True, accelerator=accel, title=title)
            group.append(s)
        section.append(group)
        win.add_child(section)
        win.present()

    def do_activate(self):
        win = L10nPreviewWindow(application=self)
        win.present()

    def _on_about(self, action, param):
        about = Adw.AboutDialog(
            application_name=_("L10n Preview"),
            application_icon="l10n-preview",
            version="0.2.2",
            developer_name="Daniel Nylander",
            developers=["Daniel Nylander <daniel@danielnylander.se>"],
            copyright="© 2026 Daniel Nylander",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/yeager/l10n-preview",
            issue_url="https://github.com/yeager/l10n-preview/issues",
            comments=_("Preview translations in context before committing"),
            translator_credits=_("Translate this app: https://www.transifex.com/danielnylander/l10n-preview/"),
        )
        about.add_link(_("Help translate"), "https://app.transifex.com/danielnylander/l10n-preview/")

        about.present(self.props.active_window)

    def do_open(self, files, n_files, hint):
        self.do_activate()
        win = self.get_active_window()
        if files:
            win._load_file(files[0].get_path())

def main():
    app = L10nPreviewApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
