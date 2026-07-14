#!/usr/bin/env node

import 'dotenv/config';
import { loadConfig, validateConfig } from './utils/config.js';
import { createLogger } from './utils/logger.js';
import { startStdioServer } from './transports/stdio.js';
import { startSseServer } from './transports/sse.js';
import { startHttpServer } from './transports/http.js';

// Global error handlers to prevent crashes
process.on('uncaughtException', error => {
  console.error('Uncaught Exception:', error);
  // Don't exit - let the server continue running
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
  // Don't exit - let the server continue running
});

// Handle CLI help
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log(`
    Codes MCP Server v${process.env.npm_package_version || '0.1.2'}

DESCRIPTION:
  MCP server for clinical table search services and medical coding systems.
  Provides access to ICD codes, LOINC, drug databases, and healthcare terminology.

USAGE:
  codes-mcp-server [options]

OPTIONS:
  --help, -h     Show this help message
  --version, -v  Show version information

ENVIRONMENT VARIABLES:
  NODE_ENV           Environment: development, production, test (default: production)
  LOG_LEVEL          Logging level: error, warn, info, debug (default: info)
  USE_HTTP           Enable HTTP transport: true/false (default: false)
  USE_SSE            Enable SSE transport: true/false (default: false)
  PORT               Server port for HTTP/SSE (default: 3000)
  
  CLINICAL API SETTINGS:
  CLINICAL_API_BASE_URL    Base URL for clinical tables API (default: https://clinicaltables.nlm.nih.gov)
  ENABLE_ICD_TOOLS         Enable ICD code search tools (default: true)
  ENABLE_LOINC_TOOLS       Enable LOINC search tools (default: true)
  ENABLE_DRUG_TOOLS        Enable medication search tools (default: true)
  ENABLE_GENOMIC_TOOLS     Enable genomic search tools (default: true)
  ENABLE_NPI_TOOLS         Enable NPI provider search tools (default: true)

EXAMPLES:
  # Run with stdio transport (default - for Cursor)
  codes-mcp-server
  
  # Run with HTTP transport for testing
  USE_HTTP=true PORT=3000 codes-mcp-server
  
  # Run with debug logging and limited tools
  LOG_LEVEL=debug ENABLE_GENOMIC_TOOLS=false codes-mcp-server

SUPPORTED CLINICAL DATA:
  • ICD-10-CM, ICD-9-CM, ICD-11 diagnosis and procedure codes
  • LOINC laboratory and clinical measurement codes
  • RxTerms prescription drug information
  • NPI healthcare provider directory
  • ClinVar, COSMIC genomic variant databases
  • Medical conditions, procedures, and terminology

For more information, visit: https://github.com/uh-joan/codes-mcp-server
`);
  process.exit(0);
}

if (process.argv.includes('--version') || process.argv.includes('-v')) {
  console.log(process.env.npm_package_version || '0.1.2');
  process.exit(0);
}

async function main() {
  const config = loadConfig();

  // Validate configuration before proceeding
  try {
    validateConfig(config);
  } catch (error) {
    console.error(
      '❌ Configuration validation failed:',
      error instanceof Error ? error.message : String(error)
    );
    process.exit(1);
  }

  const logger = createLogger(config.logLevel, config.useHttp);

  // Log configuration summary (without sensitive data)
  logger.info('🚀 Starting MCP Server', {
    name: config.name,
    version: config.version,
    environment: config.nodeEnv,
    transports: {
      http: config.useHttp,
      sse: config.useSse,
      stdio: !config.useHttp && !config.useSse,
    },
    port: config.useHttp || config.useSse ? config.port : undefined,
    features: {
      clinicalIcd: config.enableIcdTools,
      clinicalLoinc: config.enableLoincTools,
      clinicalDrugs: config.enableDrugTools,
      clinicalGenomics: config.enableGenomicTools,
      clinicalNpi: config.enableNpiTools,
      experimental: config.enableExperimentalFeatures,
      performanceMonitoring: config.enablePerformanceMonitoring,
    },
  });

  try {
    if (config.useSse) {
      await startSseServer(config, logger);
    } else if (config.useHttp) {
      await startHttpServer(config, logger);
    } else {
      await startStdioServer(config, logger);
    }
  } catch (error) {
    logger.error('Server error:', {
      error: error instanceof Error ? error.message : String(error),
    });
    process.exit(1);
  }
}

main();
