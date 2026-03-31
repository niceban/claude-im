/**
 * OpenClaw CLI Backend Plugin Entry Point
 *
 * This plugin registers a CLI Backend that uses a Python wrapper
 * to integrate with claude-node Python package.
 */
declare const _default: {
    id: string;
    name: string;
    description: string;
    configSchema: import("openclaw/plugin-sdk/plugin-entry").OpenClawPluginConfigSchema;
    register: NonNullable<import("openclaw/plugin-sdk/plugin-entry").OpenClawPluginDefinition["register"]>;
} & Pick<import("openclaw/plugin-sdk/plugin-entry").OpenClawPluginDefinition, "kind">;
export default _default;
