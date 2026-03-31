/**
 * OpenClaw CLI Backend Plugin Entry Point
 *
 * This plugin registers a CLI Backend that uses a Python wrapper
 * to integrate with claude-node Python package.
 */
import { definePluginEntry } from 'openclaw/plugin-sdk/plugin-entry';
import { claudeNodeCliBackend } from './claude-node-cli-backend.js';
export default definePluginEntry({
    id: 'openclaw-claude-bridge',
    name: 'OpenClaw claude-node Bridge',
    description: 'CLI Backend Plugin for claude-node integration',
    register(api) {
        // Register the CLI Backend for claude-node
        api.registerCliBackend(claudeNodeCliBackend);
    }
});
//# sourceMappingURL=index.js.map