/**
 * Claude Node CLI Backend Registration
 *
 * Registers a CLI Backend that uses a Python wrapper script
 * to integrate with claude-node Python package.
 */
/**
 * Claude Node CLI Backend Configuration
 *
 * Uses Python wrapper to call claude-node, providing:
 * - stdin/stdout communication (no HTTP timeout)
 * - 3-10 minute Watchdog timeout (solves MiniMax 9-15s latency issue)
 */
export declare const claudeNodeCliBackend: {
    id: string;
    config: {
        command: string;
        args: string[];
        input: "stdin";
        output: "json";
    };
};
