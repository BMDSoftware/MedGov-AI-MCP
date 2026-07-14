import { ToolRegistry } from '../types.js';
import * as nlmCtCodes from './nlm-ct-codes/index.js';

// Clinical tools registry
export const toolRegistry: ToolRegistry = {
  [nlmCtCodes.definition.name]: {
    definition: nlmCtCodes.definition,
    handler: nlmCtCodes.handler,
  },
  // Add more clinical tools here as they are implemented
};

export function getToolDefinitions() {
  return Object.values(toolRegistry).map(tool => tool.definition);
}

export function getToolHandler(toolName: string) {
  return toolRegistry[toolName]?.handler;
}

export { nlmCtCodes };
