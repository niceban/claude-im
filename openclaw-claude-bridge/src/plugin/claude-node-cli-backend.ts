/**
 * Claude Node CLI Backend Registration
 *
 * Registers a CLI Backend that uses a Python wrapper script
 * to integrate with claude-node Python package.
 */

import path from 'path';
import { fileURLToPath } from 'url';

// Get the directory of this module
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Path to the Python wrapper script (in project root)
const WRAPPER_PATH = path.resolve(__dirname, '../../../claude-node-cli-wrapper.py');

/**
 * Claude Node CLI Backend Configuration
 *
 * Uses Python wrapper to call claude-node, providing:
 * - stdin/stdout communication (no HTTP timeout)
 * - 3-10 minute Watchdog timeout (solves MiniMax 9-15s latency issue)
 */
export const claudeNodeCliBackend = {
  id: 'claude-node-cli',
  config: {
    command: 'python3',
    args: [WRAPPER_PATH],
    input: 'stdin' as const,
    output: 'json' as const,
  }
};
