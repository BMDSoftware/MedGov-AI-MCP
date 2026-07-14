import { CodeResult, Icd11MethodArgs, SearchResponse } from './types.js';
import { makeApiRequest, validateMaxList, validateOffset, validateTerms } from './utils.js';

/**
 * Search ICD-11
 * Provides access to the International Classification of Diseases and Related Health Problems (ICD-11)
 * A tool for recording, reporting and grouping conditions and factors that influence health
 * Currently using ICD-11 2023 from the World Health Organization
 */
export async function searchIcd11(args: Icd11MethodArgs): Promise<SearchResponse> {
  // Validate parameters
  const terms = validateTerms(args.terms);
  const maxList = validateMaxList(args.maxList);
  const offset = validateOffset(args.offset);

  const {
    count,
    q: additionalQuery,
    type,
    df: displayFields,
    sf: searchFields,
    cf: codeField,
    extraFields,
  } = args;

  // Set defaults for ICD-11
  const finalSearchFields = searchFields || 'code,title';
  const finalDisplayFields = displayFields || 'code,title,type';
  const finalCodeField = codeField || 'code';
  const finalType = type || 'category'; // category includes both stem and extension codes

  // Build query parameters
  const params = new URLSearchParams();
  params.append('terms', terms);
  params.append('maxList', maxList.toString());
  params.append('sf', finalSearchFields);
  params.append('df', finalDisplayFields);
  params.append('cf', finalCodeField);
  params.append('type', finalType);
  params.append('offset', offset.toString());

  if (count !== undefined) params.append('count', count.toString());
  if (additionalQuery) params.append('q', additionalQuery);
  if (extraFields) params.append('ef', extraFields);

  const url = `https://clinicaltables.nlm.nih.gov/api/icd11_codes/v3/search?${params.toString()}`;

  try {
    const response = await makeApiRequest(url);

    // ICD-11 API returns array format: [total, codes, extraData, displayData, codeSystems]
    if (!Array.isArray(response) || response.length < 4) {
      throw new Error('Invalid response format from ICD-11 API');
    }

    const [totalCount, codes, extraData, displayData] = response;

    if (!Array.isArray(codes) || !Array.isArray(displayData)) {
      throw new Error('Invalid response structure from ICD-11 API');
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
      method: 'icd-11',
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
      throw new Error(`Failed to search ICD-11: ${error.message}`);
    }
    throw new Error('Failed to search ICD-11: Unknown error');
  }
}
