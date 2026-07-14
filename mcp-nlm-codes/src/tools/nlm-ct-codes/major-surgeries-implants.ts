import { CodeResult, MajorSurgeriesImplantsMethodArgs, SearchResponse } from './types.js';
import { makeApiRequest, validateMaxList, validateOffset, validateTerms } from './utils.js';

/**
 * Search Major Surgeries and Implants
 * Provides access to about 280 major surgeries and implants procedures
 * Derived from the Regenstrief Institute's Medical Gopher program
 * Contains extensive list of full term and word synonyms
 */
export async function searchMajorSurgeriesImplants(
  args: MajorSurgeriesImplantsMethodArgs
): Promise<SearchResponse> {
  // Validate parameters
  const terms = validateTerms(args.terms);
  const maxList = validateMaxList(args.maxList);
  const offset = validateOffset(args.offset);

  const {
    count,
    q: additionalQuery,
    df: displayFields,
    sf: searchFields,
    cf: codeField,
    extraFields,
  } = args;

  // Set defaults for Major Surgeries and Implants
  const finalSearchFields =
    searchFields ||
    'consumer_name,primary_name,word_synonyms,synonyms,term_icd9_code,term_icd9_text';
  const finalDisplayFields = displayFields || 'consumer_name';
  const finalCodeField = codeField || 'key_id';

  // Build query parameters
  const params = new URLSearchParams();
  params.append('terms', terms);
  params.append('maxList', maxList.toString());
  params.append('sf', finalSearchFields);
  params.append('df', finalDisplayFields);
  params.append('cf', finalCodeField);
  params.append('offset', offset.toString());

  if (count !== undefined) params.append('count', count.toString());
  if (additionalQuery) params.append('q', additionalQuery);
  if (extraFields) params.append('ef', extraFields);

  const url = `https://clinicaltables.nlm.nih.gov/api/procedures/v3/search?${params.toString()}`;

  try {
    const response = await makeApiRequest(url);

    // Major Surgeries and Implants API returns array format: [total, codes, extraData, displayData, codeSystems]
    if (!Array.isArray(response) || response.length < 4) {
      throw new Error('Invalid response format from Major Surgeries and Implants API');
    }

    const [totalCount, codes, extraData, displayData] = response;

    if (!Array.isArray(codes) || !Array.isArray(displayData)) {
      throw new Error('Invalid response structure from Major Surgeries and Implants API');
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

    return {
      method: 'major-surgeries-implants',
      totalCount: totalCount || 0,
      results,
      pagination: {
        offset,
        count: results.length,
        hasMore: totalCount > offset + results.length,
      },
    };
  } catch (error) {
    if (error instanceof Error) {
      throw new Error(`Failed to search Major Surgeries and Implants: ${error.message}`);
    }
    throw new Error('Failed to search Major Surgeries and Implants: Unknown error');
  }
}
