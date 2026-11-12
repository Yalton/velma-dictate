import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import { Extension, gettext as _ } from 'resource:///org/gnome/shell/extensions/extension.js';

const DictateInterface = `
<node>
  <interface name="org.velma.Dictate">
    <method name="GetState">
      <arg type="s" direction="out" name="state"/>
    </method>
    <method name="GetLastTranscription">
      <arg type="s" direction="out" name="text"/>
    </method>
    <method name="GetLastStats">
      <arg type="s" direction="out" name="stats_json"/>
    </method>
    <method name="GetHistory">
      <arg type="s" direction="out" name="history_json"/>
    </method>
    <method name="GetStatus">
      <arg type="s" direction="out" name="status_json"/>
    </method>
    <method name="SetEnabled">
      <arg type="b" direction="in" name="enabled"/>
      <arg type="b" direction="out" name="result"/>
    </method>
    <method name="IsEnabled">
      <arg type="b" direction="out" name="enabled"/>
    </method>
    <signal name="StateChanged">
      <arg type="s" name="new_state"/>
    </signal>
    <signal name="TranscriptionCompleted">
      <arg type="s" name="text"/>
      <arg type="d" name="audio_duration"/>
      <arg type="d" name="latency_ms"/>
    </signal>
    <signal name="ErrorOccurred">
      <arg type="s" name="error_message"/>
    </signal>
  </interface>
</node>`;

const DictateProxy = Gio.DBusProxy.makeProxyWrapper(DictateInterface);

const VelmaIndicator = GObject.registerClass(
class VelmaIndicator extends PanelMenu.Button {
    _init(extension) {
        super._init(0.0, 'Velma Dictate Indicator');
        this._extension = extension;
        this._settings = extension.getSettings();

        this._state = 'offline';
        this._lastText = '';
        this._lastStats = null;
        this._history = [];
        this._proxy = null;
        this._signalIds = [];

        // Top bar widget layout
        this._box = new St.BoxLayout({
            style_class: 'panel-status-indicators-box velma-indicator-box',
        });

        this._icon = new St.Icon({
            icon_name: 'audio-input-microphone-symbolic',
            style_class: 'system-status-icon velma-status-offline',
        });
        this._box.add_child(this._icon);

        this._label = new St.Label({
            text: '',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'velma-indicator-label',
            visible: false,
        });
        this._box.add_child(this._label);

        this.add_child(this._box);

        this._buildMenu();
        this._initDBus();

        this._settingsSignal = this._settings.connect('changed::show-panel-text', () => {
            this._updatePanelDisplay();
        });
    }

    _buildMenu() {
        this.menu.removeAll();

        // 1. Status Section
        this._statusItem = new PopupMenu.PopupMenuItem('Velma Dictate: Checking...', { reactive: false });
        this.menu.addMenuItem(this._statusItem);

        // 2. Metrics item
        this._metricsItem = new PopupMenu.PopupMenuItem('', { reactive: false });
        this._metricsItem.actor.visible = false;
        this.menu.addMenuItem(this._metricsItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // 3. Latest Transcription Box
        this._lastHeader = new PopupMenu.PopupMenuItem(_('Latest Transcription:'), { reactive: false });
        this.menu.addMenuItem(this._lastHeader);

        this._lastTextItem = new PopupMenu.PopupMenuItem(_('(None yet)'), { reactive: true });
        this._lastTextItem.connect('activate', () => {
            if (this._lastText) {
                this._copyToClipboard(this._lastText);
            }
        });
        this.menu.addMenuItem(this._lastTextItem);

        this._copyButton = new PopupMenu.PopupImageMenuItem(_('Copy to Clipboard'), 'edit-copy-symbolic');
        this._copyButton.connect('activate', () => {
            if (this._lastText) {
                this._copyToClipboard(this._lastText);
            }
        });
        this.menu.addMenuItem(this._copyButton);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // 4. History Submenu
        this._historySubMenu = new PopupMenu.PopupSubMenuMenuItem(_('Recent Transcriptions (0)'));
        this.menu.addMenuItem(this._historySubMenu);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // 5. Controls
        this._enabledSwitch = new PopupMenu.PopupSwitchMenuItem(_('Dictation Active'), true);
        this._enabledSwitch.connect('toggled', (item, state) => {
            if (this._proxy) {
                this._proxy.SetEnabledRemote(state, (res, err) => {
                    if (err) console.error('Failed to set dictation enabled:', err);
                });
            }
        });
        this.menu.addMenuItem(this._enabledSwitch);

        // Start Daemon Button (visible when offline)
        this._startDaemonItem = new PopupMenu.PopupImageMenuItem(_('Start Daemon (systemctl)'), 'media-playback-start-symbolic');
        this._startDaemonItem.actor.visible = false;
        this._startDaemonItem.connect('activate', () => {
            try {
                Gio.Subprocess.new(['systemctl', '--user', 'restart', 'velma-dictate'], Gio.SubprocessFlags.NONE);
                this._statusItem.label.text = _('Starting daemon...');
            } catch (err) {
                console.error('Failed to restart velma-dictate daemon:', err);
            }
        });
        this.menu.addMenuItem(this._startDaemonItem);

        // Settings Dialog Button
        this._prefsItem = new PopupMenu.PopupImageMenuItem(_('Settings'), 'preferences-system-symbolic');
        this._prefsItem.connect('activate', () => {
            this._extension.openPreferences();
        });
        this.menu.addMenuItem(this._prefsItem);
    }

    _initDBus() {
        this._proxy = new DictateProxy(
            Gio.DBus.session,
            'org.velma.Dictate',
            '/org/velma/Dictate',
            (proxy, error) => {
                if (error) {
                    this._onDaemonDisconnected();
                    return;
                }

                // Connect signals
                this._signalIds.push(
                    proxy.connectSignal('StateChanged', (p, sender, [state]) => {
                        this._onStateChanged(state);
                    })
                );

                this._signalIds.push(
                    proxy.connectSignal('TranscriptionCompleted', (p, sender, [text, duration, latency]) => {
                        this._onTranscriptionCompleted(text, duration, latency);
                    })
                );

                this._signalIds.push(
                    proxy.connectSignal('ErrorOccurred', (p, sender, [error]) => {
                        this._onErrorOccurred(error);
                    })
                );

                // Watch daemon ownership
                this._signalIds.push(
                    proxy.connect('notify::g-name-owner', () => {
                        if (proxy.g_name_owner) {
                            this._onDaemonConnected();
                        } else {
                            this._onDaemonDisconnected();
                        }
                    })
                );

                if (proxy.g_name_owner) {
                    this._onDaemonConnected();
                } else {
                    this._onDaemonDisconnected();
                }
            }
        );
    }

    _onDaemonConnected() {
        this._startDaemonItem.actor.visible = false;
        this._fetchState();
        this._fetchHistory();
    }

    _onDaemonDisconnected() {
        this._state = 'offline';
        this._updatePanelDisplay();
        this._statusItem.label.text = _('Velma Daemon: Offline');
        this._metricsItem.actor.visible = false;
        this._startDaemonItem.actor.visible = true;
    }

    _fetchState() {
        if (!this._proxy) return;
        this._proxy.GetStatusRemote((result, error) => {
            if (error || !result) return;
            try {
                const status = JSON.parse(result[0]);
                this._state = status.state || 'idle';
                this._enabledSwitch.setToggleState(status.enabled ?? true);
                this._updatePanelDisplay();
            } catch (e) {
                console.error('Failed to parse status:', e);
            }
        });
    }

    _fetchHistory() {
        if (!this._proxy) return;
        this._proxy.GetHistoryRemote((result, error) => {
            if (error || !result) return;
            try {
                this._history = JSON.parse(result[0]) || [];
                this._updateHistoryUI();
            } catch (e) {
                console.error('Failed to parse history:', e);
            }
        });
    }

    _onStateChanged(state) {
        this._state = state;
        this._updatePanelDisplay();
    }

    _onTranscriptionCompleted(text, duration, latency) {
        this._lastText = text;
        this._lastStats = { audio_duration: duration, latency_ms: latency, timestamp: Date.now() / 1000 };

        // Auto-copy if preference is enabled
        if (this._settings.get_boolean('auto-copy') && text) {
            this._copyToClipboard(text);
        }

        this._updatePanelDisplay();
        this._fetchHistory();
    }

    _onErrorOccurred(errorMsg) {
        this._state = 'error';
        this._statusItem.label.text = _('Error: %s').format(errorMsg);
        this._updatePanelDisplay();
    }

    _updatePanelDisplay() {
        // Clear status styling classes
        this._icon.remove_style_class_name('velma-status-idle');
        this._icon.remove_style_class_name('velma-status-recording');
        this._icon.remove_style_class_name('velma-status-transcribing');
        this._icon.remove_style_class_name('velma-status-typing');
        this._icon.remove_style_class_name('velma-status-offline');

        const showPanelText = this._settings.get_boolean('show-panel-text');
        this._label.visible = showPanelText;

        switch (this._state) {
            case 'recording':
                this._icon.add_style_class_name('velma-status-recording');
                this._statusItem.label.text = _('🎤 Recording audio...');
                if (showPanelText) this._label.text = _('REC');
                break;
            case 'transcribing':
                this._icon.add_style_class_name('velma-status-transcribing');
                this._statusItem.label.text = _('⚡ Transcribing (MLBox)...');
                if (showPanelText) this._label.text = _('AI...');
                break;
            case 'typing':
                this._icon.add_style_class_name('velma-status-typing');
                this._statusItem.label.text = _('⌨ Typing into window...');
                if (showPanelText) this._label.text = _('Typing');
                break;
            case 'idle':
                this._icon.add_style_class_name('velma-status-idle');
                this._statusItem.label.text = _('Ready (Hold Right Ctrl to dictate)');
                if (showPanelText && this._lastStats) {
                    this._label.text = `${Math.round(this._lastStats.latency_ms)}ms`;
                } else if (showPanelText) {
                    this._label.text = '';
                }
                break;
            case 'offline':
            default:
                this._icon.add_style_class_name('velma-status-offline');
                this._statusItem.label.text = _('Velma Daemon: Offline');
                if (showPanelText) this._label.text = _('Off');
                break;
        }

        // Update metrics item
        if (this._lastStats) {
            const rt = this._lastStats.latency_ms > 0
                ? ((this._lastStats.audio_duration * 1000) / this._lastStats.latency_ms).toFixed(1)
                : '1.0';
            this._metricsItem.label.text = _('Last: %s audio in %dms (%sx real-time)').format(
                `${this._lastStats.audio_duration}s`,
                Math.round(this._lastStats.latency_ms),
                rt
            );
            this._metricsItem.actor.visible = true;
        }

        // Update latest transcription preview
        if (this._lastText) {
            const truncated = this._lastText.length > 70
                ? this._lastText.substring(0, 67) + '...'
                : this._lastText;
            this._lastTextItem.label.text = `"${truncated}"`;
            this._copyButton.actor.visible = true;
        } else {
            this._lastTextItem.label.text = _('(None yet)');
            this._copyButton.actor.visible = false;
        }
    }

    _updateHistoryUI() {
        const subMenu = this._historySubMenu.menu;
        subMenu.removeAll();

        const limit = this._settings.get_int('history-size') || 15;
        const items = this._history.slice(0, limit);

        this._historySubMenu.label.text = _('Recent Transcriptions (%d)').format(items.length);

        if (items.length === 0) {
            subMenu.addMenuItem(new PopupMenu.PopupMenuItem(_('No recent transcriptions'), { reactive: false }));
            return;
        }

        for (const item of items) {
            if (item.status === 'error') {
                const errItem = new PopupMenu.PopupMenuItem(`⚠ ${item.error || 'Transcription Error'}`, { reactive: false });
                subMenu.addMenuItem(errItem);
                continue;
            }

            const timeStr = item.timestamp
                ? new Date(item.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                : '';
            const preview = item.text.length > 45 ? item.text.substring(0, 42) + '...' : item.text;
            const labelText = `${timeStr} — "${preview}" (${Math.round(item.latency_ms || 0)}ms)`;

            const menuItem = new PopupMenu.PopupMenuItem(labelText);
            menuItem.connect('activate', () => {
                this._copyToClipboard(item.text);
            });
            subMenu.addMenuItem(menuItem);
        }
    }

    _copyToClipboard(text) {
        if (!text) return;
        const clipboard = St.Clipboard.get_default();
        clipboard.set_text(St.ClipboardType.CLIPBOARD, text);
        Main.notify(_('Velma Dictate'), _('Copied transcription to clipboard'));
    }

    destroy() {
        if (this._settingsSignal) {
            this._settings.disconnect(this._settingsSignal);
            this._settingsSignal = null;
        }

        if (this._proxy && this._signalIds.length > 0) {
            for (const id of this._signalIds) {
                try {
                    this._proxy.disconnectSignal(id);
                } catch (e) {}
            }
            this._signalIds = [];
        }

        super.destroy();
    }
});

export default class VelmaDictateExtension extends Extension {
    enable() {
        this._indicator = new VelmaIndicator(this);
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}
