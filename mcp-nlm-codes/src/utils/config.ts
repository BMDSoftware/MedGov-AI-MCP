import { ServerConfig, LogLevel } from '../types.js';

/**
 * Load configuration from environment variables with sensible defaults
 * Validates environment variables and provides type safety
 */
export function loadConfig(): ServerConfig {
  // Parse numeric environment variables with validation
  const parsePort = (value: string | undefined, defaultValue: number): number => {
    if (!value) return defaultValue;
    const parsed = parseInt(value, 10);
    if (isNaN(parsed) || parsed < 0 || parsed > 65535) {
      console.warn(`Invalid PORT value: ${value}, using default: ${defaultValue}`);
      return defaultValue;
    }
    return parsed;
  };

  const parseTimeout = (value: string | undefined, defaultValue: number): number => {
    if (!value) return defaultValue;
    const parsed = parseInt(value, 10);
    if (isNaN(parsed) || parsed < 0) {
      console.warn(`Invalid timeout value: ${value}, using default: ${defaultValue}`);
      return defaultValue;
    }
    return parsed;
  };

  const parseBoolean = (value: string | undefined, defaultValue: boolean): boolean => {
    if (!value) return defaultValue;
    return value.toLowerCase() === 'true';
  };

  // Validate log level
  const validateLogLevel = (value: string | undefined): LogLevel => {
    const validLevels: LogLevel[] = ['error', 'warn', 'info', 'debug'];
    if (!value || !validLevels.includes(value as LogLevel)) {
      return 'info';
    }
    return value as LogLevel;
  };

  return {
    name: process.env.SERVER_NAME || 'codes-mcp-server',
    version: process.env.SERVER_VERSION || '0.1.2',
    useHttp: parseBoolean(process.env.USE_HTTP, false),
    useSse: parseBoolean(process.env.USE_SSE, false),
    port: parsePort(process.env.PORT, 3000),
    ssePath: process.env.SSE_PATH || '/mcp',
    logLevel: validateLogLevel(process.env.LOG_LEVEL),

    // Additional configuration options
    nodeEnv: process.env.NODE_ENV || 'production',
    devMode: parseBoolean(process.env.DEV_MODE, false),
    debug: parseBoolean(process.env.DEBUG, false),

    // Security settings
    corsOrigins: process.env.CORS_ORIGINS?.split(',').map(o => o.trim()) || ['*'],
    requestTimeout: parseTimeout(process.env.REQUEST_TIMEOUT, 30000),
    maxRequestSize: parseTimeout(process.env.MAX_REQUEST_SIZE, 1048576),

    // Performance settings
    enablePerformanceMonitoring: parseBoolean(process.env.ENABLE_PERFORMANCE_MONITORING, false),
    metricsInterval: parseTimeout(process.env.METRICS_INTERVAL, 60000),
    maxConnections: parseTimeout(process.env.MAX_CONNECTIONS, 100),

    // Feature flags
    enableExperimentalFeatures: parseBoolean(process.env.ENABLE_EXPERIMENTAL_FEATURES, false),

    // Clinical API settings
    clinicalApiBaseUrl: process.env.CLINICAL_API_BASE_URL || 'https://clinicaltables.nlm.nih.gov',
    enableIcdTools: parseBoolean(process.env.ENABLE_ICD_TOOLS, true),
    enableLoincTools: parseBoolean(process.env.ENABLE_LOINC_TOOLS, true),
    enableDrugTools: parseBoolean(process.env.ENABLE_DRUG_TOOLS, true),
    enableGenomicTools: parseBoolean(process.env.ENABLE_GENOMIC_TOOLS, true),
    enableNpiTools: parseBoolean(process.env.ENABLE_NPI_TOOLS, true),

    // Operational settings
    healthCheckPath: process.env.HEALTH_CHECK_PATH || '/health',
    shutdownTimeout: parseTimeout(process.env.SHUTDOWN_TIMEOUT, 10000),
    processTitle: process.env.PROCESS_TITLE || 'codes-mcp-server',
  };
}

/**
 * Validate that the configuration is valid for the current environment
 */
export function validateConfig(config: ServerConfig): void {
  const errors: string[] = [];

  // Check transport configuration
  if (!config.useHttp && !config.useSse) {
    console.warn('No transport protocols enabled. Server will only work with stdio transport.');
  }

  if ((config.useHttp || config.useSse) && (!config.port || config.port === 0)) {
    errors.push('PORT must be specified when HTTP or SSE transport is enabled');
  }

  // Validate development settings
  if (config.devMode && config.nodeEnv === 'production') {
    console.warn('DEV_MODE is enabled but NODE_ENV is production. This may cause issues.');
  }

  // Check CORS configuration for production
  if (config.nodeEnv === 'production' && config.corsOrigins.includes('*')) {
    console.warn(
      'CORS is set to allow all origins (*) in production. Consider restricting to specific domains.'
    );
  }

  if (errors.length > 0) {
    throw new Error(`Configuration validation failed:\n${errors.join('\n')}`);
  }
}
