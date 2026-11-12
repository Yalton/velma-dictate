import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Gtk from 'gi://Gtk';
import { ExtensionPreferences, gettext as _ } from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

function getConfigDir() {
    return GLib.build_filenamev([GLib.get_user_config_dir(), 'velma-dictate']);
}

function getConfigFile() {
    return GLib.build_filenamev([getConfigDir(), 'config.json']);
}

function getTokenFile() {
    return GLib.build_filenamev([getConfigDir(), 'token']);
}

function loadConfig() {
    const cfg = {
        endpoint_url: 'http://192.168.50.210:8001/v1/audio/transcriptions',
        model: 'parakeet',
        language: '',
        trigger_key: 'KEY_RIGHTCTRL',
    };
    try {
        const path = getConfigFile();
        if (GLib.file_test(path, GLib.FileTest.EXISTS)) {
            const [ok, contents] = GLib.file_get_contents(path);
            if (ok) {
                const decoder = new TextDecoder();
                const data = JSON.parse(decoder.decode(contents));
                Object.assign(cfg, data);
            }
        }
    } catch (e) {
        console.error('Failed to load velma-dictate config:', e);
    }
    return cfg;
}

function loadToken() {
    try {
        const path = getTokenFile();
        if (GLib.file_test(path, GLib.FileTest.EXISTS)) {
            const [ok, contents] = GLib.file_get_contents(path);
            if (ok) {
                const decoder = new TextDecoder();
                return decoder.decode(contents).trim();
            }
        }
    } catch (e) {
        console.error('Failed to load velma-dictate token:', e);
    }
    return '';
}

function saveConfig(endpointUrl, model, language, triggerKey, token) {
    try {
        const dir = getConfigDir();
        GLib.mkdir_with_parents(dir, 0o700);

        const cfg = loadConfig();
        cfg.endpoint_url = endpointUrl.trim();
        cfg.model = model.trim();
        cfg.language = language.trim();
        cfg.trigger_key = triggerKey.trim() || 'KEY_RIGHTCTRL';

        const encoder = new TextEncoder();
        const jsonStr = JSON.stringify(cfg, null, 2) + '\n';
        const configPath = getConfigFile();
        GLib.file_set_contents(configPath, encoder.encode(jsonStr));

        const cFile = Gio.File.new_for_path(configPath);
        cFile.set_attribute_uint32(Gio.FILE_ATTRIBUTE_UNIX_MODE, 0o600, Gio.FileQueryInfoFlags.NONE, null);

        if (token !== undefined) {
            const tokenPath = getTokenFile();
            GLib.file_set_contents(tokenPath, encoder.encode(token.trim() + '\n'));
            const tFile = Gio.File.new_for_path(tokenPath);
            tFile.set_attribute_uint32(Gio.FILE_ATTRIBUTE_UNIX_MODE, 0o600, Gio.FileQueryInfoFlags.NONE, null);
        }

        return true;
    } catch (e) {
        console.error('Failed to save velma-dictate config:', e);
        return false;
    }
}

export default class VelmaDictatePreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        const currentCfg = loadConfig();
        const currentToken = loadToken();

        // 1. General Preferences Page
        const page = new Adw.PreferencesPage({
            title: _('Settings'),
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

        // Group 2: Endpoint & Model Configuration
        const apiGroup = new Adw.PreferencesGroup({
            title: _('Whisper API & Model'),
            description: _('Configure your OpenAI-compatible transcription server (e.g. Parakeet, local Whisper, or cloud API).'),
        });
        page.add(apiGroup);

        // Endpoint URL Row
        const endpointRow = new Adw.EntryRow({
            title: _('Endpoint URL'),
            text: currentCfg.endpoint_url || '',
        });
        apiGroup.add(endpointRow);

        // Model Identifier Row
        const modelRow = new Adw.EntryRow({
            title: _('Model Name'),
            text: currentCfg.model || 'parakeet',
        });
        apiGroup.add(modelRow);

        // API Key / Bearer Token Row
        const tokenRow = new Adw.PasswordEntryRow({
            title: _('API Token / Secret'),
            text: currentToken || '',
        });
        apiGroup.add(tokenRow);

        // Language Row
        const langRow = new Adw.EntryRow({
            title: _('Language (optional)'),
            text: currentCfg.language || '',
        });
        apiGroup.add(langRow);

        // Trigger Key Row
        const triggerRow = new Adw.EntryRow({
            title: _('Push-to-Talk Key (evdev name)'),
            text: currentCfg.trigger_key || 'KEY_RIGHTCTRL',
        });
        apiGroup.add(triggerRow);

        // Action Buttons Row: Save & Test
        const actionRow = new Adw.ActionRow({
            title: _('Apply Changes'),
            subtitle: _('Save configuration and test server connectivity'),
        });

        const testButton = new Gtk.Button({
            label: _('Test Connection'),
            valign: Gtk.Align.CENTER,
        });

        const saveButton = new Gtk.Button({
            label: _('Save Configuration'),
            valign: Gtk.Align.CENTER,
            css_classes: ['suggested-action'],
        });

        saveButton.connect('clicked', () => {
            const ok = saveConfig(
                endpointRow.get_text(),
                modelRow.get_text(),
                langRow.get_text(),
                triggerRow.get_text(),
                tokenRow.get_text()
            );
            if (ok) {
                actionRow.set_subtitle(_('Saved successfully! Restarting daemon...'));
                try {
                    Gio.Subprocess.new(['systemctl', '--user', 'restart', 'velma-dictate'], Gio.SubprocessFlags.NONE);
                } catch (e) {}
            } else {
                actionRow.set_subtitle(_('Failed to write configuration files.'));
            }
        });

        testButton.connect('clicked', () => {
            // First save so the test command sees the updated settings
            saveConfig(
                endpointRow.get_text(),
                modelRow.get_text(),
                langRow.get_text(),
                triggerRow.get_text(),
                tokenRow.get_text()
            );

            actionRow.set_subtitle(_('Testing endpoint connection...'));
            testButton.set_sensitive(false);

            try {
                const proc = Gio.Subprocess.new(
                    ['python3', '-m', 'velma_dictate.cli', 'test'],
                    Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
                );
                proc.communicate_utf8_async(null, null, (p, res) => {
                    testButton.set_sensitive(true);
                    try {
                        const [, stdout, stderr] = p.communicate_utf8_finish(res);
                        if (p.get_successful()) {
                            actionRow.set_subtitle(_('✅ Connection Successful! Endpoint is responsive.'));
                        } else {
                            const err = (stderr || stdout || '').trim();
                            actionRow.set_subtitle(_('❌ Test Failed: %s').format(err.substring(0, 100)));
                        }
                    } catch (err) {
                        actionRow.set_subtitle(_('❌ Test failed to execute: %s').format(err.message));
                    }
                });
            } catch (e) {
                testButton.set_sensitive(true);
                actionRow.set_subtitle(_('❌ Error launching test: %s').format(e.message));
            }
        });

        actionRow.add_suffix(testButton);
        actionRow.add_suffix(saveButton);
        apiGroup.add(actionRow);

        // Group 3: Display & Behavior
        const uiGroup = new Adw.PreferencesGroup({
            title: _('Indicator & Clipboard Options'),
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
    }
}
