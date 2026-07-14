export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: {
    type: string;
    properties: Record<string, any>;
    required?: string[];
  };
  responseSchema?: {
    type: string;
    properties: Record<string, any>;
    required?: string[];
  };
  examples?: Array<{
    description: string;
    usage: any;
    response?: any;
  }>;
}

export interface ToolHandler {
  (_args: any): Promise<any>;
}

export interface ToolRegistry {
  [toolName: string]: {
    definition: ToolDefinition;
    handler: ToolHandler;
  };
}

export type LogLevel = 'error' | 'warn' | 'info' | 'debug';

export interface ServerConfig {
  // Basic server configuration
  name: string;
  version: string;
  useHttp: boolean;
  useSse: boolean;
  port: number;
  ssePath: string;
  logLevel: LogLevel;

  // Environment configuration
  nodeEnv: string;
  devMode: boolean;
  debug: boolean;

  // Security settings
  corsOrigins: string[];
  requestTimeout: number;
  maxRequestSize: number;

  // Performance settings
  enablePerformanceMonitoring: boolean;
  metricsInterval: number;
  maxConnections: number;

  // Feature flags
  enableExperimentalFeatures: boolean;

  // Clinical API settings
  clinicalApiBaseUrl: string;
  enableIcdTools: boolean;
  enableLoincTools: boolean;
  enableDrugTools: boolean;
  enableGenomicTools: boolean;
  enableNpiTools: boolean;

  // Operational settings
  healthCheckPath: string;
  shutdownTimeout: number;
  processTitle: string;
}
