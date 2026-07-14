import { CodeResult, RxTermsMethodArgs, SearchResponse } from './types.js';
import {
  makeApiRequest,
  validateMaxList,
  validateOffset,
  validateTerms,
  validateAndProcessAdditionalQuery,
} from './utils.js';

/**
 * Search RxTerms drug interface terminology derived from RxNorm
 * Provides drug name/route pairs with associated strengths and forms for prescription writing
 */
export async function searchRxTerms(args: RxTermsMethodArgs): Promise<SearchResponse> {
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

  // Set defaults for RxTerms
  const finalSearchFields = searchFields || 'DISPLAY_NAME,DISPLAY_NAME_SYNONYM';
  const finalDisplayFields = displayFields || 'DISPLAY_NAME';
  const finalCodeField = codeField || 'DISPLAY_NAME';

  // Build query parameters
  const params = new URLSearchParams();
  params.append('terms', terms);
  params.append('maxList', maxList.toString());
  params.append('sf', finalSearchFields);
  params.append('df', finalDisplayFields);
  params.append('cf', finalCodeField);
  params.append('offset', offset.toString());

  if (count !== undefined) params.append('count', count.toString());

  // Process and validate additionalQuery to handle parentheses issues
  if (additionalQuery && typeof additionalQuery === 'string') {
    const processedQuery = validateAndProcessAdditionalQuery(additionalQuery);
    if (processedQuery !== undefined) params.append('q', processedQuery);
  }

  if (extraFields) params.append('ef', extraFields);

  const baseUrl = 'https://clinicaltables.nlm.nih.gov/api/rxterms/v3/search';
  const url = `${baseUrl}?${params.toString()}`;

  try {
    const response = await makeApiRequest(url);

    // RxTerms API returns array format: [total, codes, extraData, displayData, codeSystems]
    if (!Array.isArray(response) || response.length < 4) {
      throw new Error('Invalid response format from RxTerms API');
    }

    const [totalCount, codes, extraData, displayData] = response;

    if (!Array.isArray(codes) || !Array.isArray(displayData)) {
      throw new Error('Invalid response structure from RxTerms API');
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
      method: 'rx-terms',
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
      throw new Error(`Failed to search RxTerms: ${error.message}`);
    }
    throw new Error('Failed to search RxTerms: Unknown error');
  }
}
