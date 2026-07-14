import { CodeResult, HpoVocabularyMethodArgs } from './types.js';
import { makeApiRequest, validateAndProcessAdditionalQuery } from './utils.js';

/**
 * Search HPO (Human Phenotype Ontology) vocabulary for phenotypic abnormalities
 */
export async function searchHpoVocabulary(args: HpoVocabularyMethodArgs): Promise<CodeResult[]> {
  const {
    terms,
    maxList,
    count,
    offset,
    q: additionalQuery,
    df: displayFields,
    sf: searchFields,
    cf: codeField,
    extraFields,
  } = args;

  // Build query parameters
  const params = new URLSearchParams();
  params.append('terms', terms);

  if (maxList !== undefined) params.append('maxList', maxList.toString());
  if (count !== undefined) params.append('count', count.toString());
  if (offset !== undefined) params.append('offset', offset.toString());

  // Process and validate additionalQuery to handle parentheses issues
  if (additionalQuery && typeof additionalQuery === 'string') {
    const processedQuery = validateAndProcessAdditionalQuery(additionalQuery);
    if (processedQuery !== undefined) params.append('q', processedQuery);
  }

  if (displayFields) params.append('df', displayFields);
  if (searchFields) params.append('sf', searchFields);
  if (codeField) params.append('cf', codeField);
  if (extraFields) params.append('ef', extraFields);

  const baseUrl = 'https://clinicaltables.nlm.nih.gov/api/hpo/v3/search';
  const url = `${baseUrl}?${params.toString()}`;

  const response = await makeApiRequest(url);

  // HPO API returns array format: [total, codes, extraData, displayData, codeSystems]
  if (!Array.isArray(response) || response.length < 4) {
    throw new Error('Invalid response format from HPO API');
  }

  const [, codes, extraData, displayData] = response;

  if (!Array.isArray(codes) || !Array.isArray(displayData)) {
    throw new Error('Invalid response structure from HPO API');
  }

  const results: CodeResult[] = [];

  for (let i = 0; i < codes.length; i++) {
    const code = codes[i];
    const display = displayData[i];

    const result: CodeResult = {
      code: code,
      display: Array.isArray(display) ? display.join(' | ') : display,
    };

    // Add extra fields if available
    if (extraData && typeof extraData === 'object') {
      Object.keys(extraData).forEach(field => {
        if (Array.isArray(extraData[field]) && extraData[field][i] !== undefined) {
          (result as any)[field] = extraData[field][i];
        }
      });
    }

    results.push(result);
  }

  return results;
}
