import { ToolDefinition, ToolHandler } from '../../types.js';
import { searchIcd10Cm } from './icd-10-cm.js';
import { searchHcpcsLII } from './hcpcs-LII.js';
import { searchNpiOrganizations } from './npi-organizations.js';
import { searchNpiIndividuals } from './npi-individuals.js';
import { searchHpoVocabulary } from './hpo-vocabulary.js';
import { searchConditions } from './conditions.js';
import { searchRxTerms } from './rx-terms.js';
import { searchLoincQuestions } from './loinc-questions.js';
import { searchNcbiGenes } from './ncbi-genes.js';
import { searchMajorSurgeriesImplants } from './major-surgeries-implants.js';
import { searchIcd11 } from './icd-11.js';

export const definition: ToolDefinition = {
  name: 'nlm_ct_codes',
  description:
    "Search clinical coding systems using the NLM Clinical Tables API. Supports ICD-10-CM diagnosis codes (480+ hypertension codes, 2,466+ S72 fracture codes, etc.), ICD-11 (International Classification of Diseases 2023 from WHO), HCPCS Level II procedure/equipment codes, NPI (National Provider Identifier) organization and individual provider records from CMS, HPO (Human Phenotype Ontology) vocabulary for phenotypic abnormalities, Medical Conditions (2,400+ conditions with ICD-9/ICD-10 mappings), RxTerms drug interface terminology (drug name/route pairs with strengths and forms), LOINC Questions and Forms (universal code system for medical tests and measurements), NCBI Genes (human gene information from NCBI's Gene dataset), and Major Surgeries and Implants (280+ major surgical procedures and implants from Regenstrief Institute). Use medical terms, code patterns, provider names, specialties, phenotype terms, condition names, drug names, LOINC question/form terms, gene symbols/names, or surgical procedure names for precise searches.",
  inputSchema: {
    type: 'object',
    properties: {
      method: {
        type: 'string',
        enum: [
          'icd-10-cm',
          'icd-11',
          'hcpcs-LII',
          'npi-organizations',
          'npi-individuals',
          'hpo-vocabulary',
          'conditions',
          'rx-terms',
          'loinc-questions',
          'ncbi-genes',
          'major-surgeries-implants',
        ],
        description:
          "The coding system to search: 'icd-10-cm' for ICD-10-CM diagnosis codes, 'icd-11' for ICD-11 (International Classification of Diseases 2023 from WHO), 'hcpcs-LII' for HCPCS Level II procedure codes, 'npi-organizations' for National Provider Identifier organization records, 'npi-individuals' for National Provider Identifier individual provider records, 'hpo-vocabulary' for HPO (Human Phenotype Ontology) phenotypic abnormality terms, 'conditions' for Medical Conditions from Regenstrief Institute (2,400+ conditions with ICD-9/ICD-10 mappings), 'rx-terms' for RxTerms drug interface terminology (drug name/route pairs with strengths and forms), 'loinc-questions' for LOINC Questions and Forms (universal code system for medical tests and measurements), 'ncbi-genes' for NCBI Genes (human gene information from NCBI's Gene dataset), 'major-surgeries-implants' for Major Surgeries and Implants (280+ major surgical procedures and implants from Regenstrief Institute).",
      },
      terms: {
        type: 'string',
        description:
          "The search string to find matches. For ICD-10-CM: use medical terms (e.g., 'hypertension', 'pneumonia') or code patterns (e.g., 'S72' for femur fractures, 'E11' for diabetes). For ICD-11: use medical terms (e.g., 'heart', 'blood', 'pneumonia') or ICD-11 codes (e.g., '1B12.0', 'QB25'). For HCPCS: use procedure/equipment terms (e.g., 'glucose', 'wheelchair'). For NPI Organizations: use organization names, specialties, or NPI numbers (e.g., 'MAYO CLINIC', 'cardiology', '1234567890'). For NPI Individuals: use provider names, specialties, or NPI numbers (e.g., 'john smith', 'cardiologist', '1234567890'). For HPO Vocabulary: use phenotype terms (e.g., 'blood pressure', 'seizure', 'intellectual disability'). For Conditions: use medical condition names (e.g., 'gastroenteritis', 'diabetes', 'hypertension'). For RxTerms: use drug names (e.g., 'arava', 'articaine', 'lisinopril'). For LOINC Questions: use question/form terms (e.g., 'walk', 'blood pressure', 'vital signs') or LOINC codes (e.g., '45593-1'). For NCBI Genes: use gene symbols (e.g., 'BRCA1', 'TP53', 'MTX'), gene names, or descriptions. For Major Surgeries and Implants: use surgical procedure names (e.g., 'gastrostomy', 'bypass', 'implant', 'gastrectomy'). Multiple words use implicit AND logic.",
      },
      maxList: {
        type: 'number',
        description: 'Maximum number of results to return (1-500). Default is 7.',
        minimum: 1,
        maximum: 500,
        default: 7,
      },
      searchFields: {
        type: 'string',
        description:
          "Comma-separated list of fields to search in. For ICD-10-CM: 'code' (for specific code patterns like 'S72'), 'name' (for condition names), or 'code,name' (default - searches both). For HCPCS: 'code' (exact codes like 'E0470'), 'short_desc' (brief equipment names), 'long_desc' (detailed specifications), 'display' (standard descriptions). For NPI Organizations: 'NPI' (NPI numbers), 'name.full' (organization names), 'provider_type' (specialties), 'addr_practice.full' (practice addresses). For NPI Individuals: 'NPI' (NPI numbers), 'name.full' (provider names), 'provider_type' (specialties), 'addr_practice.full' (practice addresses). For HPO Vocabulary: 'id' (HPO term IDs like 'HP:0001871'), 'name' (phenotype names), 'synonym.term' (synonym terms), or 'id,name,synonym.term' (default - searches all). For Conditions: 'consumer_name' (consumer-friendly names), 'primary_name' (medical names), 'word_synonyms' (word synonyms), 'synonyms' (term synonyms), 'term_icd9_code' (ICD-9 codes), 'term_icd9_text' (ICD-9 text), or 'consumer_name,primary_name,word_synonyms,synonyms,term_icd9_code,term_icd9_text' (default - searches all). For RxTerms: 'DISPLAY_NAME' (drug name/route pairs), 'DISPLAY_NAME_SYNONYM' (synonyms), or 'DISPLAY_NAME,DISPLAY_NAME_SYNONYM' (default - searches both). Default: varies by method.",
      },
      displayFields: {
        type: 'string',
        description:
          "Comma-separated list of fields to display in results. For ICD-10-CM: 'code', 'name'. For HCPCS: 'code' (procedure code), 'display' (standard description), 'short_desc' (brief description), 'long_desc' (detailed specifications). For NPI Organizations: 'NPI' (NPI number), 'name.full' (organization name), 'provider_type' (specialty), 'addr_practice.full' (practice address). For NPI Individuals: 'NPI' (NPI number), 'name.full' (provider name), 'provider_type' (specialty), 'addr_practice.full' (practice address). For HPO Vocabulary: 'id' (HPO term ID), 'name' (phenotype name), 'definition' (phenotype definition). For Conditions: 'consumer_name' (consumer-friendly name), 'primary_name' (medical name), 'term_icd9_code' (ICD-9 code), 'key_id' (unique identifier). For RxTerms: 'DISPLAY_NAME' (drug name/route pairs). Default: varies by method.",
      },
      extraFields: {
        type: 'string',
        description:
          'For HCPCS, NPI Organizations, NPI Individuals, HPO Vocabulary, Conditions, and RxTerms: Comma-separated list of additional fields to return. For HCPCS: short_desc, long_desc, add_dt, term_dt, act_eff_dt, obsolete, is_noc. For NPI Organizations and Individuals: gender (individuals only), name.last, name.first, name.middle, name.credential, addr_practice.line1, addr_practice.city, addr_practice.state, addr_mailing.full, other_ids, licenses, misc.auth_official.last, misc.enumeration_date, misc.last_update_date, etc. For HPO Vocabulary: definition, def_xref, created_by, creation_date, comment, is_obsolete, replaced_by, consider, alt_id, synonym, is_a, xref, property. For Conditions: primary_name, consumer_name, icd10cm_codes, icd10cm, term_icd9_code, term_icd9_text, word_synonyms, synonyms, info_link_data. For RxTerms: STRENGTHS_AND_FORMS, RXCUIS, SXDG_RXCUI, DISPLAY_NAME_SYNONYM. See documentation for complete field list.',
      },
      additionalQuery: {
        type: 'string',
        description:
          "Optional additional query string to further constrain results. Supports Elasticsearch query syntax with advanced boolean expressions. The tool automatically handles complex parentheses grouping and transforms them for optimal API compatibility. Examples: Simple filtering: 'addr_practice.state:CA' or 'obsolete:false'. Boolean expressions: 'gender:F AND addr_practice.state:CA'. Complex queries with parentheses: 'addr_practice.state:CA AND (addr_practice.city:\"Los Angeles\" OR addr_practice.city:\"San Francisco\")' or 'hospital OR medical AND (addr_practice.state:CA OR addr_practice.state:NY)'. For HCPCS: 'is_noc:false' (exclude generic codes), 'obsolete:false' (active codes only). For NPI Organizations and Individuals: 'addr_practice.state:CA' (California providers), 'provider_type:Physician*' (physician specialties), 'gender:M' (male individuals only). For ICD-10-CM: use for advanced pattern matching. For ICD-11: 'type:stem' (stem codes only), 'type:extension' (extension codes only), 'chapter:1' (specific chapter), or any field-based filtering. For HPO Vocabulary: 'is_obsolete:false' (active terms only), 'id:HP\\:000*' (specific HPO ID patterns), or any field-based filtering. For Conditions: 'term_icd9_code:558*' (specific ICD-9 code patterns), 'icd10cm_codes:*E11*' (ICD-10 code filtering), or any field-based filtering. For RxTerms: use for drug name or route filtering, or any field-based filtering. For LOINC Questions: 'isCopyrighted:false' (exclude copyrighted items), 'datatype:CNE' (list questions only), 'COMPONENT:*pressure*' (component filtering), or field-based filtering. For NCBI Genes: 'chromosome:1' (specific chromosome), 'type_of_gene:protein-coding' (gene type filtering), 'Symbol:BRCA*' (symbol patterns), or any field-based filtering. For Major Surgeries and Implants: 'term_icd9_code:*' (procedures with ICD-9 codes), 'primary_name:*bypass*' (specific procedure patterns), or any field-based filtering.",
      },
      offset: {
        type: 'number',
        description:
          'Starting result number for pagination (0-based). Use with maxList to paginate through large result sets (e.g., S72 codes have 2,466+ results). Default is 0.',
        minimum: 0,
        default: 0,
      },
      count: {
        type: 'number',
        description:
          'For HCPCS, NPI Organizations, NPI Individuals, HPO Vocabulary, Conditions, and RxTerms: Page size for pagination (1-500). Use with offset for large result sets (e.g., 325 wheelchair codes, thousands of providers by specialty, thousands of HPO phenotype terms, 2,400+ medical conditions, thousands of drug terms). Different from maxList which limits total results returned. Default is 7.',
        minimum: 1,
        maximum: 500,
        default: 7,
      },
    },
    required: ['method', 'terms'],
  },
  responseSchema: {
    type: 'object',
    properties: {
      method: {
        type: 'string',
        description: 'The coding system that was searched',
      },
      totalCount: {
        type: 'number',
        description: 'Total number of matching results on the server',
      },
      results: {
        type: 'array',
        description: 'Array of codes and descriptions',
        items: {
          type: 'object',
          properties: {
            code: { type: 'string', description: 'The medical code or NPI number' },
            name: { type: 'string', description: 'Description/name (for ICD-10-CM)' },
            display: { type: 'string', description: 'Display description (for HCPCS)' },
            shortDescription: { type: 'string', description: 'Short description (for HCPCS)' },
            longDescription: { type: 'string', description: 'Long description (for HCPCS)' },
            addDate: { type: 'string', description: 'Date code was added (for HCPCS)' },
            termDate: { type: 'string', description: 'Date code was terminated (for HCPCS)' },
            actualEffectiveDate: {
              type: 'string',
              description: 'Actual effective date (for HCPCS)',
            },
            obsolete: { type: 'boolean', description: 'Whether the code is obsolete (for HCPCS)' },
            isNoc: {
              type: 'boolean',
              description: 'Whether the code is Not Otherwise Classified (for HCPCS)',
            },

            // NPI Organizations and Individuals fields
            npi: {
              type: 'string',
              description:
                'National Provider Identifier number (for NPI Organizations and Individuals)',
            },
            fullName: {
              type: 'string',
              description: 'Provider full name (for NPI Organizations and Individuals)',
            },
            providerType: {
              type: 'string',
              description: 'Provider specialty type (for NPI Organizations and Individuals)',
            },
            practiceAddress: {
              type: 'string',
              description: 'Full practice address (for NPI Organizations and Individuals)',
            },
            gender: { type: 'string', description: 'Provider gender (for NPI Individuals only)' },
            lastName: {
              type: 'string',
              description: 'Provider last name (for NPI Organizations and Individuals)',
            },
            firstName: {
              type: 'string',
              description: 'Provider first name (for NPI Organizations and Individuals)',
            },
            middleName: {
              type: 'string',
              description: 'Provider middle name (for NPI Organizations and Individuals)',
            },
            credential: {
              type: 'string',
              description: 'Provider credential (for NPI Organizations and Individuals)',
            },
            practiceCity: {
              type: 'string',
              description: 'Practice address city (for NPI Organizations and Individuals)',
            },
            practiceState: {
              type: 'string',
              description: 'Practice address state (for NPI Organizations and Individuals)',
            },
            practicePhone: {
              type: 'string',
              description: 'Practice phone number (for NPI Organizations and Individuals)',
            },
            mailingAddress: {
              type: 'string',
              description: 'Full mailing address (for NPI Organizations and Individuals)',
            },
            otherIds: {
              type: 'array',
              description: 'Other identifier objects (for NPI Organizations and Individuals)',
            },
            licenses: {
              type: 'array',
              description:
                'License objects with taxonomy and Medicare data (for NPI Organizations and Individuals)',
            },
            authorizedOfficialLast: {
              type: 'string',
              description: 'Authorized official last name (for NPI Organizations and Individuals)',
            },
            enumerationDate: {
              type: 'string',
              description: 'NPI enumeration date (for NPI Organizations and Individuals)',
            },
            lastUpdateDate: {
              type: 'string',
              description: 'Last update date (for NPI Organizations and Individuals)',
            },

            // HPO Vocabulary fields
            id: { type: 'string', description: 'HPO term ID (for HPO Vocabulary)' },
            definition: { type: 'string', description: 'HPO term definition (for HPO Vocabulary)' },
            defXref: {
              type: 'array',
              description: 'List of xrefs from definition field (for HPO Vocabulary)',
            },
            createdBy: { type: 'string', description: 'Created by field (for HPO Vocabulary)' },
            creationDate: {
              type: 'string',
              description: 'Creation date field (for HPO Vocabulary)',
            },
            comment: { type: 'string', description: 'Comment field (for HPO Vocabulary)' },
            isObsolete: {
              type: 'boolean',
              description: 'Whether the HPO term is obsolete (for HPO Vocabulary)',
            },
            replacedBy: { type: 'string', description: 'Replaced by id (for HPO Vocabulary)' },
            consider: {
              type: 'array',
              description: 'List of ids from consider field (for HPO Vocabulary)',
            },
            altId: { type: 'array', description: 'List of alternative ids (for HPO Vocabulary)' },
            synonym: {
              type: 'array',
              description: 'List of synonyms with term, relation, type, xref (for HPO Vocabulary)',
            },
            isA: {
              type: 'array',
              description: 'List of super concept ids with id and name (for HPO Vocabulary)',
            },
            xref: {
              type: 'array',
              description: 'List of xrefs with id and name (for HPO Vocabulary)',
            },
            property: {
              type: 'array',
              description:
                'List of properties with name, value, data_type, xref (for HPO Vocabulary)',
            },

            // Medical Conditions fields
            primaryName: {
              type: 'string',
              description: 'The name of the medical condition (for Conditions)',
            },
            consumerName: {
              type: 'string',
              description: 'Consumer-friendly version of the disease name (for Conditions)',
            },
            keyId: {
              type: 'string',
              description: 'Unique identifier (code) for the medical condition (for Conditions)',
            },
            icd10cmCodes: {
              type: 'string',
              description: 'Comma-separated list of suggested ICD-10-CM codes (for Conditions)',
            },
            icd10cm: {
              type: 'array',
              description:
                'Array of code and display name pairs for ICD-10-CM codes (for Conditions)',
            },
            termIcd9Code: {
              type: 'string',
              description: 'The ICD-9-CM code for the term (for Conditions)',
            },
            termIcd9Text: {
              type: 'string',
              description: 'The ICD-9-CM display text for the term (for Conditions)',
            },
            wordSynonyms: {
              type: 'array',
              description: 'Synonyms for each of the words in the term (for Conditions)',
            },
            synonyms: {
              type: 'array',
              description: 'Synonyms for the whole term (for Conditions)',
            },
            infoLinkData: {
              type: 'array',
              description: 'Links to information about the condition (for Conditions)',
            },

            // RxTerms fields
            STRENGTHS_AND_FORMS: {
              type: 'array',
              description: 'List of strength and form combination strings (for RxTerms)',
            },
            RXCUIS: {
              type: 'array',
              description:
                'RxNorm unique identifiers for DISPLAY_NAME + strength-form combinations (for RxTerms)',
            },
            SXDG_RXCUI: {
              type: 'string',
              description: 'RxNorm unique identifier for the DISPLAY_NAME entity (for RxTerms)',
            },
            DISPLAY_NAME_SYNONYM: {
              type: 'array',
              description: 'Synonyms for the drug display name (for RxTerms)',
            },

            // LOINC Questions and Forms fields
            text: {
              type: 'string',
              description: 'The text of the question or form name (for LOINC Questions)',
            },
            LOINC_NUM: {
              type: 'string',
              description: 'The LOINC code for the question or form (for LOINC Questions)',
            },
            RELATEDNAMES2: {
              type: 'string',
              description: 'Word-level synonyms (for LOINC Questions)',
            },
            PROPERTY: { type: 'string', description: 'LOINC property (for LOINC Questions)' },
            METHOD_TYP: { type: 'string', description: 'LOINC method type (for LOINC Questions)' },
            AnswerLists: {
              type: 'array',
              description: 'Answer lists with applicable contexts (for LOINC Questions)',
            },
            units: {
              type: 'array',
              description: 'UCUM-style units for numeric values (for LOINC Questions)',
            },
            datatype: {
              type: 'string',
              description:
                'Computed data type: CNE, CWE, ST, REAL, DT, TM, Ratio (for LOINC Questions)',
            },
            isCopyrighted: {
              type: 'boolean',
              description: 'True if item has external copyright (for LOINC Questions)',
            },
            containsCopyrighted: {
              type: 'boolean',
              description: 'True if item or contained item has copyright (for LOINC Questions)',
            },
            CONSUMER_NAME: {
              type: 'string',
              description: 'Consumer-friendly name (for LOINC Questions)',
            },
            LONG_COMMON_NAME: {
              type: 'string',
              description: 'Long common name (for LOINC Questions)',
            },
            SHORTNAME: { type: 'string', description: 'Short name (for LOINC Questions)' },
            COMPONENT: { type: 'string', description: 'Component name (for LOINC Questions)' },
            EXTERNAL_COPYRIGHT_NOTICE: {
              type: 'string',
              description: 'External copyright notice (for LOINC Questions)',
            },
            EXTERNAL_COPYRIGHT_LINK: {
              type: 'string',
              description: 'External copyright link identifier (for LOINC Questions)',
            },

            // NCBI Genes fields
            GeneID: { type: 'string', description: 'Unique gene identifier (for NCBI Genes)' },
            HGNC_ID: {
              type: 'string',
              description: 'HGNC identifier if available (for NCBI Genes)',
            },
            Symbol: { type: 'string', description: 'Default gene symbol (for NCBI Genes)' },
            Synonyms: {
              type: 'string',
              description: 'Bar-delimited unofficial symbols (for NCBI Genes)',
            },
            dbXrefs: {
              type: 'string',
              description: 'Bar-delimited cross-references to other databases (for NCBI Genes)',
            },
            chromosome: { type: 'string', description: 'Chromosome location (for NCBI Genes)' },
            map_location: {
              type: 'string',
              description: 'Cytogenetic map location (for NCBI Genes)',
            },
            description: { type: 'string', description: 'Descriptive gene name (for NCBI Genes)' },
            type_of_gene: {
              type: 'string',
              description: 'Gene type classification (for NCBI Genes)',
            },
            na_symbol: {
              type: 'string',
              description: 'Nomenclature authority symbol (for NCBI Genes)',
            },
            na_name: {
              type: 'string',
              description: 'Nomenclature authority name (for NCBI Genes)',
            },
            Other_designations: {
              type: 'string',
              description: 'Pipe-delimited alternate descriptions (for NCBI Genes)',
            },
            Modification_date: {
              type: 'string',
              description: 'Last update date in YYYYMMDD format (for NCBI Genes)',
            },
            _code_system: { type: 'string', description: 'Code system indicator (for NCBI Genes)' },
            _code: {
              type: 'string',
              description: 'Unique ID based on cf parameter (for NCBI Genes)',
            },

            // Major Surgeries and Implants fields
            procedure_primary_name: {
              type: 'string',
              description: 'The name of the procedure (for Major Surgeries and Implants)',
            },
            procedure_consumer_name: {
              type: 'string',
              description:
                'Consumer-friendly version of the procedure name (for Major Surgeries and Implants)',
            },
            procedure_key_id: {
              type: 'string',
              description:
                'Unique identifier (code) for the procedure (for Major Surgeries and Implants)',
            },
            procedure_icd9_code: {
              type: 'string',
              description: 'ICD-9-CM code for the term (for Major Surgeries and Implants)',
            },
            procedure_icd9_text: {
              type: 'string',
              description: 'ICD-9-CM display text for the term (for Major Surgeries and Implants)',
            },
            procedure_word_synonyms: {
              type: 'string',
              description: 'Synonyms for each word in the term (for Major Surgeries and Implants)',
            },
            procedure_synonyms: {
              type: 'string',
              description: 'Synonyms for the whole term (for Major Surgeries and Implants)',
            },
            procedure_info_links: {
              type: 'array',
              items: { type: 'string' },
              description:
                'Links to information about the procedure (for Major Surgeries and Implants)',
            },

            // ICD-11 fields
            icd11_title: { type: 'string', description: 'The title/name for the ICD-11 code' },
            icd11_definition: {
              type: 'string',
              description: 'The definition text for the ICD-11 code',
            },
            icd11_type: { type: 'string', description: "Code type: 'stem' or 'extension'" },
            icd11_chapter: {
              type: 'string',
              description: 'The ICD-11 chapter number the code appears in',
            },
            icd11_entityId: {
              type: 'string',
              description: 'The entity id (URI) in the linearization context',
            },
            icd11_source: {
              type: 'string',
              description: 'The Foundation URI for the code as defined by WHO',
            },
            icd11_browserUrl: {
              type: 'string',
              description: 'The Foundation URI as defined by WHO',
            },
            icd11_parent: {
              type: 'string',
              description: 'The Linearization (release) URI as defined by WHO',
            },
          },
        },
      },
      pagination: {
        type: 'object',
        description: 'Pagination information',
        properties: {
          offset: { type: 'number', description: 'Current offset' },
          count: { type: 'number', description: 'Number of results returned' },
          hasMore: { type: 'boolean', description: 'Whether more results are available' },
        },
      },
    },
    required: ['method', 'totalCount', 'results', 'pagination'],
  },
  examples: [
    {
      description: 'Search ICD-10-CM for hypertension-related diagnoses',
      usage: {
        method: 'icd-10-cm',
        terms: 'hypertension',
        maxList: 10,
      },
      response: {
        method: 'icd-10-cm',
        totalCount: 80,
        results: [
          { code: 'I15.0', name: 'Renovascular hypertension' },
          { code: 'I1A.0', name: 'Resistant hypertension' },
          { code: 'I97.3', name: 'Postprocedural hypertension' },
          { code: 'I10', name: 'Essential (primary) hypertension' },
        ],
        pagination: { offset: 0, count: 10, hasMore: true },
      },
    },
    {
      description: 'Search ICD-10-CM for specific code patterns (femur fractures)',
      usage: {
        method: 'icd-10-cm',
        terms: 'S72',
        searchFields: 'code',
        maxList: 5,
      },
      response: {
        method: 'icd-10-cm',
        totalCount: 2466,
        results: [
          {
            code: 'S72.001A',
            name: 'Fracture of unspecified part of neck of right femur, initial encounter for closed fracture',
          },
          {
            code: 'S72.001B',
            name: 'Fracture of unspecified part of neck of right femur, initial encounter for open fracture type I or II',
          },
        ],
        pagination: { offset: 0, count: 5, hasMore: true },
      },
    },
    {
      description: 'Search ICD-10-CM with pagination for pneumonia codes',
      usage: {
        method: 'icd-10-cm',
        terms: 'pneumonia',
        maxList: 15,
        offset: 10,
      },
      response: {
        method: 'icd-10-cm',
        totalCount: 77,
        results: [
          { code: 'J12.89', name: 'Other viral pneumonia' },
          { code: 'J15.9', name: 'Unspecified bacterial pneumonia' },
          { code: 'J84.116', name: 'Cryptogenic organizing pneumonia' },
        ],
        pagination: { offset: 10, count: 7, hasMore: true },
      },
    },
    {
      description: 'Search HCPCS for oxygen equipment (basic search)',
      usage: {
        method: 'hcpcs-LII',
        terms: 'oxygen',
        maxList: 7,
      },
      response: {
        method: 'hcpcs-LII',
        totalCount: 51,
        results: [
          { code: 'C1300', display: 'Hyperbaric oxygen' },
          { code: 'E1390', display: 'Oxygen concentrator' },
          { code: 'E1392', display: 'Portable oxygen concentrator' },
          { code: 'A4616', display: 'Tubing (oxygen) per foot' },
        ],
        pagination: { offset: 0, count: 7, hasMore: true },
      },
    },
    {
      description: 'Search HCPCS wheelchairs with detailed descriptions',
      usage: {
        method: 'hcpcs-LII',
        terms: 'wheelchair',
        extraFields: 'short_desc,long_desc,is_noc,obsolete',
        maxList: 6,
      },
      response: {
        method: 'hcpcs-LII',
        totalCount: 325,
        results: [
          {
            code: 'K0001',
            display: 'Standard wheelchair',
            shortDescription: 'Standard wheelchair',
            longDescription: 'Standard wheelchair',
            isNoc: 'false',
            obsolete: 'false',
          },
          {
            code: 'E0961',
            display: 'Wheelchair brake extension',
            shortDescription: 'Wheelchair brake extension',
            longDescription:
              'Manual wheelchair accessory, wheel lock brake extension (handle), each',
            isNoc: 'false',
            obsolete: 'false',
          },
        ],
        pagination: { offset: 0, count: 6, hasMore: true },
      },
    },
    {
      description: 'Search HCPCS by specific code with historical data',
      usage: {
        method: 'hcpcs-LII',
        terms: 'E0470',
        searchFields: 'code',
        extraFields: 'short_desc,long_desc,add_dt,obsolete',
        maxList: 3,
      },
      response: {
        method: 'hcpcs-LII',
        totalCount: 1,
        results: [
          {
            code: 'E0470',
            display: 'Rad w/o backup non-inv intfc',
            shortDescription: 'Rad w/o backup non-inv intfc',
            longDescription:
              'Respiratory assist device, bi-level pressure capability, without backup rate feature, used with noninvasive interface, e.g., nasal or facial mask',
            addDate: '20040101',
            obsolete: 'false',
          },
        ],
        pagination: { offset: 0, count: 1, hasMore: false },
      },
    },
    {
      description: 'Search HCPCS infusion pumps with advanced filtering',
      usage: {
        method: 'hcpcs-LII',
        terms: 'infusion pump',
        searchFields: 'short_desc,long_desc',
        additionalQuery: 'is_noc:false',
        extraFields: 'short_desc,long_desc,is_noc',
        maxList: 5,
      },
      response: {
        method: 'hcpcs-LII',
        totalCount: 42,
        results: [
          {
            code: 'C1772',
            display: 'Infusion pump, programmable',
            shortDescription: 'Infusion pump, programmable',
            longDescription: 'Infusion pump, programmable (implantable)',
            isNoc: 'false',
          },
          {
            code: 'E1520',
            display: 'Heparin infusion pump',
            shortDescription: 'Heparin infusion pump',
            longDescription: 'Heparin infusion pump for hemodialysis',
            isNoc: 'false',
          },
        ],
        pagination: { offset: 0, count: 5, hasMore: true },
      },
    },
    {
      description: 'Search HCPCS with pagination and complete metadata',
      usage: {
        method: 'hcpcs-LII',
        terms: 'ventilator',
        additionalQuery: 'obsolete:false',
        extraFields: 'add_dt,act_eff_dt,obsolete,is_noc',
        offset: 0,
        maxList: 6,
      },
      response: {
        method: 'hcpcs-LII',
        totalCount: 9,
        results: [
          {
            code: 'E1029',
            display: 'W/c vent tray fixed',
            addDate: '20040101',
            actualEffectiveDate: '20140401',
            obsolete: 'false',
            isNoc: 'false',
          },
          {
            code: 'E0465',
            display: 'Home vent invasive interface',
            addDate: '20160101',
            actualEffectiveDate: '20160101',
            obsolete: 'false',
            isNoc: 'false',
          },
        ],
        pagination: { offset: 0, count: 6, hasMore: true },
      },
    },
    {
      description: 'Search NPI Organizations for healthcare providers related to Bethesda',
      usage: {
        method: 'npi-organizations',
        terms: 'bethesda',
        maxList: 3,
      },
    },
    {
      description: 'Search NPI Organizations for MAYO CLINIC with detailed information',
      usage: {
        method: 'npi-organizations',
        terms: 'MAYO CLINIC',
        extraFields: 'addr_practice.city,addr_practice.state,misc.enumeration_date',
        maxList: 2,
      },
    },
    {
      description: 'Search NPI Organizations by specialty with state filtering',
      usage: {
        method: 'npi-organizations',
        terms: 'cardiology',
        additionalQuery: 'addr_practice.state:CA',
        extraFields: 'addr_practice.city,addr_practice.state,name.credential',
        maxList: 3,
      },
    },
    {
      description: 'Search NPI Organizations by exact NPI number with comprehensive details',
      usage: {
        method: 'npi-organizations',
        terms: '1114343860',
        searchFields: 'NPI',
        extraFields:
          'name.last,name.first,name.credential,addr_practice.phone,addr_mailing.full,misc.auth_official.last,misc.auth_official.first,misc.enumeration_date,misc.last_update_date,other_ids',
        maxList: 1,
      },
    },
    {
      description: 'Search NPI Organizations by specialty type (Emergency Medicine)',
      usage: {
        method: 'npi-organizations',
        terms: 'Emergency Medicine',
        searchFields: 'provider_type',
        extraFields: 'addr_practice.city,addr_practice.state',
        maxList: 3,
      },
    },
    {
      description: 'Search NPI Organizations with pagination (hospitals)',
      usage: {
        method: 'npi-organizations',
        terms: 'hospital',
        count: 3,
        offset: 10,
        extraFields: 'addr_practice.state',
      },
    },
    {
      description: 'Search NPI Individuals for providers in Bethesda area',
      usage: {
        method: 'npi-individuals',
        terms: 'john bethesda',
        maxList: 5,
      },
    },
    {
      description:
        'Search NPI Individuals for female physicians in California with gender filtering',
      usage: {
        method: 'npi-individuals',
        terms: 'physician',
        additionalQuery: 'gender:F AND addr_practice.state:CA',
        extraFields: 'gender,name.credential,addr_practice.city,addr_practice.state',
        maxList: 4,
      },
    },
    {
      description: 'Search NPI Individuals by exact NPI number with comprehensive details',
      usage: {
        method: 'npi-individuals',
        terms: '1760880173',
        searchFields: 'NPI',
        extraFields:
          'gender,name.last,name.first,name.credential,addr_practice.phone,addr_mailing.full,misc.enumeration_date,misc.last_update_date,other_ids',
        maxList: 1,
      },
    },
    {
      description: 'Search NPI Individuals for emergency medicine physicians by specialty',
      usage: {
        method: 'npi-individuals',
        terms: 'Emergency Medicine',
        searchFields: 'provider_type',
        extraFields: 'gender,name.credential,addr_practice.city,addr_practice.state',
        maxList: 3,
      },
    },
    {
      description: 'Search NPI Individuals with pagination (nurse providers)',
      usage: {
        method: 'npi-individuals',
        terms: 'nurse',
        count: 4,
        offset: 10,
        extraFields: 'gender,addr_practice.state',
      },
    },
    {
      description: 'Search NPI Individuals for cardiologists with detailed license information',
      usage: {
        method: 'npi-individuals',
        terms: 'cardiologist',
        extraFields: 'gender,name.credential,licenses,other_ids,misc.enumeration_date',
        maxList: 2,
      },
    },
    {
      description: 'Search NPI Individuals by name with detailed name field breakdown',
      usage: {
        method: 'npi-individuals',
        terms: 'smith',
        searchFields: 'name.full',
        extraFields:
          'name.last,name.first,name.middle,name.prefix,name.suffix,name_other.full,addr_practice.city,addr_practice.state',
        maxList: 3,
      },
    },
    {
      description: 'Search HPO Vocabulary for blood pressure related phenotypes',
      usage: {
        method: 'hpo-vocabulary',
        terms: 'blood pressure',
        maxList: 5,
      },
    },
    {
      description: 'Search HPO Vocabulary for specific HPO term ID',
      usage: {
        method: 'hpo-vocabulary',
        terms: 'HP:0001871',
        searchFields: 'id',
        extraFields: 'definition,is_a,synonym',
        maxList: 1,
      },
    },
    {
      description: 'Search HPO Vocabulary for intellectual disability with detailed information',
      usage: {
        method: 'hpo-vocabulary',
        terms: 'intellectual disability',
        extraFields: 'definition,synonym,is_a,xref',
        maxList: 3,
      },
    },
    {
      description: 'Search HPO Vocabulary for seizure phenotypes with filtering',
      usage: {
        method: 'hpo-vocabulary',
        terms: 'seizure',
        additionalQuery: 'is_obsolete:false',
        extraFields: 'definition,alt_id,consider',
        maxList: 4,
      },
    },
    {
      description: 'Search HPO Vocabulary with pagination for growth abnormalities',
      usage: {
        method: 'hpo-vocabulary',
        terms: 'growth',
        count: 5,
        offset: 10,
        extraFields: 'definition,is_a',
      },
    },
    {
      description: 'Search HPO Vocabulary for cardiac abnormalities with comprehensive metadata',
      usage: {
        method: 'hpo-vocabulary',
        terms: 'cardiac',
        extraFields: 'definition,created_by,creation_date,comment,property',
        maxList: 3,
      },
    },
    {
      description: 'Search Medical Conditions for gastroenteritis-related conditions',
      usage: {
        method: 'conditions',
        terms: 'gastroenteritis',
        maxList: 5,
      },
    },
    {
      description: 'Search Medical Conditions by ICD-9 code and display detailed information',
      usage: {
        method: 'conditions',
        terms: 'gastroenteritis',
        displayFields: 'term_icd9_code,primary_name',
        extraFields: 'term_icd9_text,icd10cm_codes,synonyms',
        maxList: 3,
      },
    },
    {
      description: 'Search Medical Conditions by consumer-friendly name only',
      usage: {
        method: 'conditions',
        terms: 'diabetes',
        searchFields: 'consumer_name',
        extraFields: 'primary_name,icd10cm_codes,term_icd9_code',
        maxList: 4,
      },
    },
    {
      description: 'Search Medical Conditions with ICD-9 code filtering',
      usage: {
        method: 'conditions',
        terms: 'colitis',
        additionalQuery: 'term_icd9_code:558*',
        extraFields: 'term_icd9_text,icd10cm,word_synonyms',
        maxList: 3,
      },
    },
    {
      description: 'Search Medical Conditions with pagination and complete metadata',
      usage: {
        method: 'conditions',
        terms: 'hypertension',
        count: 4,
        offset: 5,
        extraFields: 'primary_name,icd10cm_codes,synonyms,info_link_data',
      },
    },
    {
      description: 'Search Medical Conditions by specific key_id with comprehensive details',
      usage: {
        method: 'conditions',
        terms: '4458',
        searchFields: 'key_id',
        extraFields:
          'primary_name,consumer_name,term_icd9_code,term_icd9_text,icd10cm_codes,icd10cm,word_synonyms,synonyms',
        maxList: 1,
      },
    },
    {
      description: 'Search RxTerms for basic drug information (ARAVA)',
      usage: {
        method: 'rx-terms',
        terms: 'arava',
        maxList: 5,
      },
    },
    {
      description: 'Search RxTerms for drug with strength and form information',
      usage: {
        method: 'rx-terms',
        terms: 'arava',
        extraFields: 'STRENGTHS_AND_FORMS',
        maxList: 3,
      },
    },
    {
      description: 'Search RxTerms for drug with complete information including RxCUIs',
      usage: {
        method: 'rx-terms',
        terms: 'articaine',
        extraFields: 'STRENGTHS_AND_FORMS,RXCUIS,SXDG_RXCUI',
        maxList: 2,
      },
    },
    {
      description: 'Search RxTerms for common drug name with synonyms',
      usage: {
        method: 'rx-terms',
        terms: 'lisinopril',
        extraFields: 'STRENGTHS_AND_FORMS,DISPLAY_NAME_SYNONYM',
        maxList: 4,
      },
    },
    {
      description: 'Search RxTerms by drug display name only',
      usage: {
        method: 'rx-terms',
        terms: 'insulin',
        searchFields: 'DISPLAY_NAME',
        extraFields: 'STRENGTHS_AND_FORMS',
        maxList: 3,
      },
    },
    {
      description: 'Search RxTerms with pagination for antibiotic medications',
      usage: {
        method: 'rx-terms',
        terms: 'antibiotic',
        count: 5,
        offset: 10,
        extraFields: 'STRENGTHS_AND_FORMS,RXCUIS',
      },
    },
    {
      description: 'Search LOINC Questions for walking-related assessments',
      usage: {
        method: 'loinc-questions',
        terms: 'walk',
        type: 'question',
        maxList: 7,
      },
    },
    {
      description: 'Search LOINC Questions with copyright information',
      usage: {
        method: 'loinc-questions',
        terms: 'walk',
        type: 'question',
        extraFields: 'isCopyrighted,EXTERNAL_COPYRIGHT_NOTICE',
        maxList: 5,
      },
    },
    {
      description: 'Search LOINC Forms for vital signs assessments',
      usage: {
        method: 'loinc-questions',
        terms: 'vital signs',
        type: 'form',
        available: true,
        maxList: 3,
      },
    },
    {
      description: 'Search LOINC Questions for blood pressure measurements with complete metadata',
      usage: {
        method: 'loinc-questions',
        terms: 'blood pressure',
        type: 'question',
        extraFields: 'LOINC_NUM,COMPONENT,datatype,units,AnswerLists',
        maxList: 4,
      },
    },
    {
      description: 'Search LOINC Questions excluding copyrighted items',
      usage: {
        method: 'loinc-questions',
        terms: 'depression',
        type: 'question',
        excludeCopyrighted: true,
        extraFields: 'CONSUMER_NAME,SHORTNAME,isCopyrighted',
        maxList: 5,
      },
    },
    {
      description: 'Search LOINC Questions by specific LOINC code',
      usage: {
        method: 'loinc-questions',
        terms: '45593-1',
        searchFields: 'LOINC_NUM',
        extraFields: 'text,CONSUMER_NAME,datatype,EXTERNAL_COPYRIGHT_NOTICE',
        maxList: 1,
      },
    },
    {
      description: 'Search LOINC Forms and sections with filtering by data type',
      usage: {
        method: 'loinc-questions',
        terms: 'assessment',
        type: 'form_and_section',
        available: true,
        additionalQuery: 'datatype:CNE',
        extraFields: 'COMPONENT,METHOD_TYP,datatype',
        maxList: 4,
      },
    },
    {
      description: 'Search LOINC Questions with pagination for laboratory tests',
      usage: {
        method: 'loinc-questions',
        terms: 'glucose',
        type: 'question',
        count: 6,
        offset: 5,
        extraFields: 'PROPERTY,METHOD_TYP,units,RELATEDNAMES2',
      },
    },
    {
      description: 'Search NCBI Genes for basic gene information (MTX genes)',
      usage: {
        method: 'ncbi-genes',
        terms: 'MTX',
        maxList: 5,
      },
    },
    {
      description: 'Search NCBI Genes for BRCA1 with detailed information',
      usage: {
        method: 'ncbi-genes',
        terms: 'BRCA1',
        extraFields: 'HGNC_ID,chromosome,map_location,type_of_gene,dbXrefs',
        maxList: 3,
      },
    },
    {
      description: 'Search NCBI Genes by specific gene symbol',
      usage: {
        method: 'ncbi-genes',
        terms: 'TP53',
        searchFields: 'Symbol',
        extraFields: 'description,chromosome,Synonyms,Other_designations',
        maxList: 1,
      },
    },
    {
      description: 'Search NCBI Genes for insulin-related genes with filtering',
      usage: {
        method: 'ncbi-genes',
        terms: 'insulin',
        additionalQuery: 'type_of_gene:protein-coding',
        extraFields: 'Symbol,chromosome,type_of_gene,na_symbol',
        maxList: 4,
      },
    },
    {
      description: 'Search NCBI Genes by chromosome with comprehensive metadata',
      usage: {
        method: 'ncbi-genes',
        terms: 'dystrophin',
        extraFields: 'GeneID,HGNC_ID,chromosome,map_location,Synonyms,Modification_date',
        maxList: 2,
      },
    },
    {
      description: 'Search NCBI Genes with pagination for cancer-related genes',
      usage: {
        method: 'ncbi-genes',
        terms: 'oncogene',
        count: 3,
        offset: 10,
        extraFields: 'Symbol,description,type_of_gene,dbXrefs',
      },
    },
    {
      description: 'Search Major Surgeries and Implants for gastric procedures',
      usage: {
        method: 'major-surgeries-implants',
        terms: 'gast',
        maxList: 7,
      },
    },
    {
      description: 'Search Major Surgeries and Implants for bypass procedures with details',
      usage: {
        method: 'major-surgeries-implants',
        terms: 'bypass',
        extraFields: 'primary_name,term_icd9_code,term_icd9_text,synonyms',
        maxList: 5,
      },
    },
    {
      description: 'Search Major Surgeries and Implants for specific implant procedures',
      usage: {
        method: 'major-surgeries-implants',
        terms: 'implant',
        searchFields: 'consumer_name,primary_name',
        extraFields: 'word_synonyms,info_link_data',
        maxList: 4,
      },
    },
    {
      description: 'Search Major Surgeries and Implants with ICD-9 code filtering',
      usage: {
        method: 'major-surgeries-implants',
        terms: 'surgery',
        additionalQuery: 'term_icd9_code:*',
        extraFields: 'primary_name,term_icd9_code,term_icd9_text',
        maxList: 6,
      },
    },
    {
      description: 'Search Major Surgeries and Implants for heart procedures with pagination',
      usage: {
        method: 'major-surgeries-implants',
        terms: 'heart',
        count: 3,
        offset: 5,
        extraFields: 'consumer_name,primary_name,synonyms',
      },
    },
    {
      description: 'Search Major Surgeries and Implants for specific procedure patterns',
      usage: {
        method: 'major-surgeries-implants',
        terms: 'arthroscopy',
        additionalQuery: 'primary_name:*arthroscopy*',
        extraFields: 'primary_name,consumer_name,word_synonyms,term_icd9_code',
        maxList: 3,
      },
    },
    {
      description: 'Search ICD-11 for heart-related conditions',
      usage: {
        method: 'icd-11',
        terms: 'heart',
        maxList: 7,
      },
    },
    {
      description: 'Search ICD-11 for specific codes with browser URLs',
      usage: {
        method: 'icd-11',
        terms: 'blood',
        displayFields: 'code,browserUrl',
        maxList: 5,
      },
    },
    {
      description: 'Search ICD-11 with stem codes only and extra metadata',
      usage: {
        method: 'icd-11',
        terms: 'pneumonia',
        type: 'stem',
        extraFields: 'title,definition,chapter,entityId',
        maxList: 4,
      },
    },
    {
      description: 'Search ICD-11 with extension codes filtering',
      usage: {
        method: 'icd-11',
        terms: 'pain',
        type: 'extension',
        additionalQuery: 'chapter:21',
        extraFields: 'type,source,parent',
        maxList: 6,
      },
    },
    {
      description: 'Search ICD-11 for tuberculosis with comprehensive metadata',
      usage: {
        method: 'icd-11',
        terms: 'tuberculosis',
        extraFields: 'title,definition,type,chapter,browserUrl,entityId,source',
        maxList: 3,
      },
    },
    {
      description: 'Search ICD-11 with pagination for diabetes-related codes',
      usage: {
        method: 'icd-11',
        terms: 'diabetes',
        count: 4,
        offset: 8,
        extraFields: 'title,type,chapter',
      },
    },
    {
      description: 'Search NPI Organizations with complex boolean query using parentheses',
      usage: {
        method: 'npi-organizations',
        terms: 'hospital OR medical',
        additionalQuery: 'addr_practice.state:CA AND (addr_practice.city:"Los Angeles" OR addr_practice.city:"San Francisco")',
        extraFields: 'provider_type,addr_practice.city,addr_practice.state,name.full,NPI',
        maxList: 5,
      },
    },
    {
      description: 'Search NPI Organizations with complex OR-AND grouping',
      usage: {
        method: 'npi-organizations',
        terms: 'cardiology OR neurology',
        additionalQuery: 'hospital OR clinic AND (addr_practice.state:CA OR addr_practice.state:NY)',
        extraFields: 'provider_type,addr_practice.city,addr_practice.state',
        maxList: 8,
      },
    },
    {
      description: 'Search NPI Organizations with multiple location filtering',
      usage: {
        method: 'npi-organizations',
        terms: 'medical center',
        additionalQuery: '(addr_practice.city:"New York" OR addr_practice.city:"Chicago" OR addr_practice.city:"Boston") AND provider_type:Hospital*',
        extraFields: 'addr_practice.city,addr_practice.state,provider_type',
        maxList: 6,
      },
    },
    {
      description: 'Search NPI Individuals with complex location and specialty filtering',
      usage: {
        method: 'npi-individuals',
        terms: 'physician',
        additionalQuery: 'gender:F AND (addr_practice.state:CA AND (addr_practice.city:"Los Angeles" OR addr_practice.city:"San Diego"))',
        extraFields: 'gender,name.credential,addr_practice.city,addr_practice.state,provider_type',
        maxList: 5,
      },
    },
    {
      description: 'Search NPI Individuals with nested boolean expressions',
      usage: {
        method: 'npi-individuals',
        terms: 'cardiology OR neurology',
        additionalQuery: '(gender:M OR gender:F) AND (addr_practice.state:TX OR (addr_practice.state:CA AND provider_type:Physician*))',
        extraFields: 'gender,provider_type,addr_practice.city,addr_practice.state',
        maxList: 7,
      },
    },
    {
      description: 'Search HPO Vocabulary with complex filtering and boolean logic',
      usage: {
        method: 'hpo-vocabulary',
        terms: 'cardiac OR heart',
        additionalQuery: 'is_obsolete:false AND (id:HP\\:000* OR (name:*abnormal* AND property:*phenotype*))',
        extraFields: 'definition,is_a,synonym,property',
        maxList: 6,
      },
    },
  ],
};

export const handler: ToolHandler = async (args: any) => {
  // Validate required parameters
  if (!args.method || typeof args.method !== 'string') {
    throw new Error('The "method" parameter is required and must be a string');
  }

  if (
    ![
      'icd-10-cm',
      'icd-11',
      'hcpcs-LII',
      'npi-organizations',
      'npi-individuals',
      'hpo-vocabulary',
      'conditions',
      'rx-terms',
      'loinc-questions',
      'ncbi-genes',
      'major-surgeries-implants',
    ].includes(args.method)
  ) {
    throw new Error(
      'The "method" parameter must be one of: "icd-10-cm", "icd-11", "hcpcs-LII", "npi-organizations", "npi-individuals", "hpo-vocabulary", "conditions", "rx-terms", "loinc-questions", "ncbi-genes", or "major-surgeries-implants"'
    );
  }

  // Route to the appropriate method implementation
  switch (args.method) {
    case 'icd-10-cm':
      return await searchIcd10Cm(args);

    case 'icd-11':
      return await searchIcd11(args);

    case 'hcpcs-LII':
      return await searchHcpcsLII(args);

    case 'npi-organizations':
      return await searchNpiOrganizations(args);

    case 'npi-individuals':
      return await searchNpiIndividuals(args);

    case 'hpo-vocabulary':
      return await searchHpoVocabulary(args);

    case 'conditions':
      return await searchConditions(args);

    case 'rx-terms':
      return await searchRxTerms(args);

    case 'loinc-questions':
      return await searchLoincQuestions(args);

    case 'ncbi-genes':
      return await searchNcbiGenes(args);

    case 'major-surgeries-implants':
      return await searchMajorSurgeriesImplants(args);

    default:
      throw new Error(`Unsupported method: ${args.method}`);
  }
};
