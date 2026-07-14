// Shared types for NLM Clinical Tables API methods

export interface BaseMethodArgs {
  terms: string;
  maxList?: number;
  offset?: number;
  searchFields?: string;
  displayFields?: string;
  additionalQuery?: string;
}

export interface IcdMethodArgs extends BaseMethodArgs {
  // ICD-10-CM specific parameters (no additional ones currently)
}

export interface HcpcsMethodArgs extends BaseMethodArgs {
  count?: number;
  extraFields?: string;
}

export interface NpiMethodArgs extends BaseMethodArgs {
  count?: number;
  extraFields?: string;
}

export interface NpiIndividualsMethodArgs extends BaseMethodArgs {
  count?: number;
  extraFields?: string;
}

export interface HpoVocabularyMethodArgs extends BaseMethodArgs {
  count?: number;
  q?: string; // Additional query string (corresponds to additionalQuery in base)
  df?: string; // Display fields
  sf?: string; // Search fields
  cf?: string; // Code field
  extraFields?: string; // Extra fields (ef parameter in API)
}

export interface ConditionsMethodArgs extends BaseMethodArgs {
  count?: number;
  q?: string; // Additional query string (corresponds to additionalQuery in base)
  df?: string; // Display fields
  sf?: string; // Search fields
  cf?: string; // Code field
  extraFields?: string; // Extra fields (ef parameter in API)
}

export interface RxTermsMethodArgs extends BaseMethodArgs {
  count?: number;
  q?: string; // Additional query string (corresponds to additionalQuery in base)
  df?: string; // Display fields
  sf?: string; // Search fields
  cf?: string; // Code field
  extraFields?: string; // Extra fields (ef parameter in API)
}

export interface LoincQuestionsMethodArgs extends BaseMethodArgs {
  count?: number;
  q?: string; // Additional query string (corresponds to additionalQuery in base)
  df?: string; // Display fields
  sf?: string; // Search fields
  cf?: string; // Code field
  extraFields?: string; // Extra fields (ef parameter in API)
  type?: 'question' | 'form' | 'form_and_section' | 'panel'; // Type of LOINC item to search
  available?: boolean; // For forms, limit to those with available definitions
  excludeCopyrighted?: boolean; // Exclude copyrighted items
}

export interface NcbiGenesMethodArgs extends BaseMethodArgs {
  count?: number;
  q?: string; // Additional query string (corresponds to additionalQuery in base)
  df?: string; // Display fields
  sf?: string; // Search fields
  cf?: string; // Code field
  extraFields?: string; // Extra fields (ef parameter in API)
}

export interface MajorSurgeriesImplantsMethodArgs extends BaseMethodArgs {
  count?: number;
  q?: string; // Additional query string (corresponds to additionalQuery in base)
  df?: string; // Display fields
  sf?: string; // Search fields
  cf?: string; // Code field
  extraFields?: string; // Extra fields (ef parameter in API)
}

export interface Icd11MethodArgs extends BaseMethodArgs {
  count?: number;
  q?: string; // Additional query string (corresponds to additionalQuery in base)
  type?: 'stem' | 'extension' | 'category'; // Code type filter
  df?: string; // Display fields
  sf?: string; // Search fields
  cf?: string; // Code field
  extraFields?: string; // Extra fields (ef parameter in API)
}

export interface CodeResult {
  code: string;
  name?: string; // For ICD-10-CM
  display?: string; // For HCPCS
  shortDescription?: string; // For HCPCS
  longDescription?: string; // For HCPCS
  addDate?: string; // For HCPCS
  termDate?: string; // For HCPCS
  actualEffectiveDate?: string; // For HCPCS
  obsolete?: boolean; // For HCPCS
  isNoc?: boolean; // For HCPCS

  // For NPI Organizations
  npi?: string; // NPI number
  fullName?: string; // Provider full name
  providerType?: string; // Provider specialty type
  practiceAddress?: string; // Full practice address

  // For NPI Individuals (additional field)
  gender?: string; // Provider gender (for individuals only)

  // For HPO Vocabulary
  id?: string; // HPO term id
  definition?: string; // HPO term definition
  defXref?: any[]; // List of xrefs from definition field
  createdBy?: string; // Created by field
  creationDate?: string; // Creation date field
  comment?: string; // Comment field
  isObsolete?: boolean; // Obsolete flag
  replacedBy?: string; // Replaced by id
  consider?: string[]; // List of ids from consider field
  altId?: string[]; // List of alternative ids
  synonym?: any[]; // List of synonyms with term, relation, type, xref
  isA?: any[]; // List of super concept ids with id and name
  xref?: any[]; // List of xrefs with id and name
  property?: any[]; // List of properties with name, value, data_type, xref

  // For Medical Conditions
  primaryName?: string; // The name of the medical condition
  consumerName?: string; // Consumer-friendly version of the disease name
  keyId?: string; // Unique identifier (code) for the medical condition
  icd10cmCodes?: string; // Comma-separated list of suggested ICD-10-CM codes
  icd10cm?: any[]; // Array of code and display name pairs for ICD-10-CM codes
  termIcd9Code?: string; // The ICD-9-CM code for the term
  termIcd9Text?: string; // The ICD-9-CM display text for the term
  wordSynonyms?: string[]; // Synonyms for each of the words in the term
  synonyms?: string[]; // Synonyms for the whole term
  infoLinkData?: any[]; // Links to information about the condition

  // Extended NPI fields (when extraFields is used)
  lastName?: string;
  firstName?: string;
  middleName?: string;
  credential?: string;
  namePrefix?: string;
  nameSuffix?: string;
  practiceAddressLine1?: string;
  practiceAddressLine2?: string;
  practiceCity?: string;
  practiceState?: string;
  practiceZip?: string;
  practicePhone?: string;
  practiceFax?: string;
  practiceCountry?: string;
  mailingAddress?: string;
  mailingAddressLine1?: string;
  mailingAddressLine2?: string;
  mailingCity?: string;
  mailingState?: string;
  mailingZip?: string;
  mailingPhone?: string;
  mailingFax?: string;
  mailingCountry?: string;
  otherNameFull?: string;
  otherNameLast?: string;
  otherNameFirst?: string;
  otherNameMiddle?: string;
  otherNameCredential?: string;
  otherNamePrefix?: string;
  otherNameSuffix?: string;
  otherIds?: any[]; // Array of other ID objects
  licenses?: any[]; // Array of license objects
  authorizedOfficialLast?: string;
  authorizedOfficialFirst?: string;
  authorizedOfficialMiddle?: string;
  authorizedOfficialCredential?: string;
  authorizedOfficialTitle?: string;
  authorizedOfficialPrefix?: string;
  authorizedOfficialSuffix?: string;
  authorizedOfficialPhone?: string;
  replacementNPI?: string;
  ein?: string;
  enumerationDate?: string;
  lastUpdateDate?: string;
  isSoleProprietor?: boolean;
  isOrgSubpart?: boolean;
  parentLBN?: string;
  parentTIN?: string;

  // RxTerms fields
  STRENGTHS_AND_FORMS?: string[] | string;
  RXCUIS?: string[] | string;
  SXDG_RXCUI?: string;
  DISPLAY_NAME_SYNONYM?: string[] | string;

  // LOINC Questions and Forms fields
  text?: string; // The text of the question or form name
  LOINC_NUM?: string; // The LOINC code for the question or form
  RELATEDNAMES2?: string; // Word-level synonyms
  PROPERTY?: string; // LOINC property
  METHOD_TYP?: string; // LOINC method type
  AnswerLists?: any[]; // Answer lists with applicable contexts
  units?: any[]; // UCUM-style units for numeric values
  datatype?: string; // Computed data type (CNE, CWE, ST, REAL, DT, TM, Ratio)
  isCopyrighted?: boolean; // True if item has external copyright
  containsCopyrighted?: boolean; // True if item or contained item has copyright
  CONSUMER_NAME?: string; // Consumer-friendly name
  LONG_COMMON_NAME?: string; // Long common name
  SHORTNAME?: string; // Short name
  COMPONENT?: string; // Component name
  EXTERNAL_COPYRIGHT_NOTICE?: string; // External copyright notice
  EXTERNAL_COPYRIGHT_LINK?: string; // External copyright link identifier

  // NCBI Genes fields
  GeneID?: string; // Unique gene identifier
  HGNC_ID?: string; // HGNC identifier if available
  Symbol?: string; // Default gene symbol
  Synonyms?: string; // Bar-delimited unofficial symbols
  dbXrefs?: string; // Bar-delimited cross-references to other databases
  chromosome?: string; // Chromosome location
  map_location?: string; // Cytogenetic map location
  description?: string; // Descriptive gene name
  type_of_gene?: string; // Gene type classification
  na_symbol?: string; // Nomenclature authority symbol
  na_name?: string; // Nomenclature authority name
  Other_designations?: string; // Pipe-delimited alternate descriptions
  Modification_date?: string; // Last update date (YYYYMMDD format)
  _code_system?: string; // Code system indicator (not searchable)
  _code?: string; // Unique ID based on cf parameter (not searchable)

  // Major Surgeries and Implants fields
  procedure_primary_name?: string; // The name of the procedure (for Major Surgeries and Implants)
  procedure_consumer_name?: string; // Consumer-friendly version of the procedure name (for Major Surgeries and Implants)
  procedure_key_id?: string; // Unique identifier (code) for the procedure (for Major Surgeries and Implants)
  procedure_icd9_code?: string; // ICD-9-CM code for the term (for Major Surgeries and Implants)
  procedure_icd9_text?: string; // ICD-9-CM display text for the term (for Major Surgeries and Implants)
  procedure_word_synonyms?: string; // Synonyms for each word in the term (for Major Surgeries and Implants)
  procedure_synonyms?: string; // Synonyms for the whole term (for Major Surgeries and Implants)
  procedure_info_links?: string[]; // Links to information about the procedure (for Major Surgeries and Implants)

  // ICD-11 fields
  icd11_title?: string; // The title/name for the ICD-11 code
  icd11_definition?: string; // The definition text for the ICD-11 code
  icd11_type?: string; // Code type: "stem" or "extension"
  icd11_chapter?: string; // The ICD-11 chapter number the code appears in
  icd11_entityId?: string; // The entity id (URI) in the linearization context
  icd11_source?: string; // The Foundation URI for the code as defined by WHO
  icd11_browserUrl?: string; // The Foundation URI as defined by WHO
  icd11_parent?: string; // The Linearization (release) URI as defined by WHO
}

export interface SearchResponse {
  method: string;
  totalCount: number;
  results: CodeResult[];
  pagination: {
    offset: number;
    count: number;
    hasMore: boolean;
  };
}

export interface ApiResponse {
  totalCount: number;
  codes: string[];
  extraData?: Record<string, any[]>;
  displayStrings: string[][];
}
