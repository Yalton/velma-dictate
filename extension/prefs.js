import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import Gtk from 'gi://Gtk';
import { ExtensionPreferences, gettext as _ } from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class VelmaDictatePreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();

        // 1. General Preferences Page
        const page = new Adw.PreferencesPage({
            title: _('General'),
            icon_name: 'audio-input-microphone-symbolic',
        });
        window.add(page);

        // Group 1: Service Status
        const serviceGroup = new Adw.PreferencesGroup({
            title: _('Daemon Status'),
            description: _('velma-dictate runs as a background user systemd service.'),
        });
        page.add(serviceGroup);

        const statusRow = new Adw.ActionRow({
            title: _('Background Daemon'),
            subtitle: _('Checking service status...'),
        });

        const restartButton = new Gtk.Button({
            label: _('Restart Service'),
            valign: Gtk.Align.CENTER,
            css_classes: ['suggested-action'],
        });

        restartButton.connect('clicked', () => {
            try {
                Gio.Subprocess.new(
                    ['systemctl', '--user', 'restart', 'velma-dictate'],
                    Gio.SubprocessFlags.NONE
                );
                statusRow.set_subtitle(_('Restart command sent (systemctl --user restart velma-dictate)'));
            } catch (e) {
                statusRow.set_subtitle(_('Error restarting service: %s').format(e.message));
            }
        });

        statusRow.add_suffix(restartButton);
        serviceGroup.add(statusRow);

        // Check if service is active via systemctl is-active
        try {
            const proc = Gio.Subprocess.new(
                ['systemctl', '--user', 'is-active', 'velma-dictate'],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
            );
            proc.communicate_utf8_async(null, null, (p, res) => {
                try {
                    const [, stdout] = p.communicate_utf8_finish(res);
                    const state = (stdout || '').trim();
                    if (state === 'active') {
                        statusRow.set_subtitle(_('Running and healthy (active)'));
                    } else {
                        statusRow.set_subtitle(_('Inactive (%s) — click Restart to launch').format(state || 'not running'));
                    }
                } catch (err) {
                    statusRow.set_subtitle(_('Could not determine service state'));
                }
            });
        } catch (e) {
            statusRow.set_subtitle(_('Service check unavailable'));
        }

        // Group 2: Display & Behavior
        const uiGroup = new Adw.PreferencesGroup({
            title: _('Indicator & Clipboard'),
            description: _('Configure panel indicator and clipboard behavior.'),
        });
        page.add(uiGroup);

        // Switch: Show text in panel
        const panelTextRow = new Adw.SwitchRow({
            title: _('Show Latency & State in Top Bar'),
            subtitle: _('Display live state badge or milliseconds next to the microphone icon'),
        });
        settings.bind('show-panel-text', panelTextRow, 'active', Gio.SettingsBindFlags.DEFAULT);
        uiGroup.add(panelTextRow);

        // Switch: Auto-copy to clipboard
        const autoCopyRow = new Adw.SwitchRow({
            title: _('Auto-Copy to Clipboard'),
            subtitle: _('Automatically copy every transcription to the clipboard in addition to typing'),
        });
        settings.bind('auto-copy', autoCopyRow, 'active', Gio.SettingsBindFlags.DEFAULT);
        uiGroup.add(autoCopyRow);

        // SpinRow: History Size
        const historyRow = new Adw.SpinRow({
            title: _('Recent Transcriptions in Menu'),
            subtitle: _('Number of recent transcriptions preserved in the drop-down menu'),
            adjustment: new Gtk.Adjustment({
                lower: 5,
                upper: 50,
                step_increment: 5,
                page_increment: 10,
            }),
        });
        settings.bind('history-size', historyRow, 'value', Gio.SettingsBindFlags.DEFAULT);
        uiGroup.add(historyRow);

        // Group 3: Backend & Keybinding Info
        const infoGroup = new Adw.PreferencesGroup({
            title: _('Backend Configuration'),
            description: _('Configure model, server endpoint, and trigger hotkeys via ~/.config/velma-dictate/config.json'),
        });
        page.add(infoGroup);

        const configPathRow = new Adw.ActionRow({
            title: _('Configuration File'),
            subtitle: '~/.config/velma-dictate/config.json',
        });
        infoGroup.add(configPathRow);

        const shortcutRow = new Adw.ActionRow({
            title: _('Default Push-to-Talk Shortcut'),
            subtitle: _('Hold Right Ctrl, speak, release to transcribe.'),
        });
        infoGroup.add(shortcutRow);
    }
}
