# Unofficial NLM Codes MCP Server

An MCP server providing access to clinical table search services and medical coding systems. This server enables AI assistants to query various clinical data tables including ICD codes, LOINC, HCPCS, medication databases, and other healthcare terminology systems through the National Library of Medicine's Clinical Tables API.

## Supported Clinical Data Sources

This server provides a unified tool to search and access various clinical coding systems and medical data tables:

### Medical Coding Systems
- **ICD-10-CM** - International Classification of Diseases, 10th Revision, Clinical Modification
- **ICD-11** - WHO's latest International Classification of Diseases (2023)
- **HCPCS Level II** - Healthcare Common Procedure Coding System

### Healthcare Providers
- **NPI Organizations** - National Provider Identifier lookup for healthcare organizations
- **NPI Individuals** - National Provider Identifier lookup for individual providers

### Clinical Terminologies & Conditions
- **HPO Vocabulary** - Human Phenotype Ontology for standardized phenotypic abnormalities
- **Medical Conditions** - Curated list of 2,400+ medical conditions with ICD-9/ICD-10 mappings
- **Major Surgeries & Implants** - 280+ major surgical procedures and implants

### Medication & Drug Information
- **RxTerms** - Drug interface terminology with name/route pairs, strengths and forms

### Laboratory & Testing
- **LOINC Questions** - Logical Observation Identifiers Names and Codes for medical tests and measurements

### Genomics & Genetics
- **NCBI Genes** - Human gene information from NCBI's Gene dataset

## Usage

   ```json
   {
  "codes-mcp-server": {
      "command": "node",
      "args": ["/path/to/codes-mcp-server/build/index.js"],
      "env": {}
     }
   }
   ```

## Available Tool

### Unified Clinical Search Tool: `nlm_ct_codes`

This server provides **one unified tool** that handles all clinical data searches through different methods:

**Tool Name**: `nlm_ct_codes`

**Description**: Search clinical coding systems using the NLM Clinical Tables API. Supports multiple medical coding systems, provider databases, and clinical terminologies.

**Usage Example**:
```javascript
// Search ICD-10-CM codes for hypertension
{
  "method": "icd-10-cm",
  "terms": "hypertension",
  "maxList": 10
}

// Search for healthcare providers in California
{
  "method": "npi-organizations", 
  "terms": "cardiology",
  "additionalQuery": "addr_practice.state:CA",
  "maxList": 5
}

// Search HCPCS codes for wheelchairs
{
  "method": "hcpcs-LII",
  "terms": "wheelchair",
  "maxList": 15
}

// Complex boolean query with parentheses (automatically optimized)
{
  "method": "npi-organizations",
  "terms": "hospital OR medical",
  "additionalQuery": "addr_practice.state:CA AND (addr_practice.city:\"Los Angeles\" OR addr_practice.city:\"San Francisco\")",
  "extraFields": "provider_type,addr_practice.city,addr_practice.state,name.full,NPI",
  "maxList": 5
}
```

### Advanced Query Capabilities

The `additionalQuery` parameter supports sophisticated boolean expressions with parentheses grouping. The tool automatically detects and optimizes complex queries for best API compatibility:

**Simple Filtering**:
- `"addr_practice.state:CA"` - Single condition
- `"obsolete:false"` - Boolean filtering

**Boolean Expressions**:
- `"gender:F AND addr_practice.state:CA"` - AND operations
- `"cardiology OR neurology"` - OR operations

**Complex Parentheses Grouping** (automatically optimized):
- `"addr_practice.state:CA AND (addr_practice.city:\"Los Angeles\" OR addr_practice.city:\"San Francisco\")"` 
- `"hospital OR medical AND (addr_practice.state:CA OR addr_practice.state:NY)"`
- `"(provider_type:Physician* OR provider_type:Nurse*) AND addr_practice.state:TX"`

The tool transforms complex parentheses expressions using boolean algebra for optimal performance while maintaining the intended logic.

**Supported Methods**:
- `icd-10-cm` - Search ICD-10-CM diagnosis codes
- `icd-11` - Search ICD-11 codes
- `hcpcs-LII` - Search HCPCS Level II procedure/equipment codes
- `npi-organizations` - Search healthcare organizations
- `npi-individuals` - Search individual healthcare providers
- `hpo-vocabulary` - Search phenotypic abnormality terms
- `conditions` - Search medical conditions
- `rx-terms` - Search prescription drug terminology
- `loinc-questions` - Search LOINC codes and forms
- `ncbi-genes` - Search gene information
- `major-surgeries-implants` - Search surgical procedures and implants

**Parameters**:
- `method` (required): The coding system to search
- `terms` (required): Search query string
- `maxList`: Maximum results to return (1-500, default: 7)
- `searchFields`: Comma-separated fields to search in
- `displayFields`: Comma-separated fields to display
- `extraFields`: Additional fields to include in results
- `additionalQuery`: Elasticsearch query for advanced filtering
- `offset`: Starting result number for pagination (default: 0)
- `count`: Page size for pagination (1-500, default: 7)

## Resources

- [Clinical Table Search Service](https://clinicaltables.nlm.nih.gov/)
- [Healthcare Terminology Standards](https://www.nlm.nih.gov/research/umls/)
- [FHIR Terminology Services](https://hl7.org/fhir/terminology-service.html)