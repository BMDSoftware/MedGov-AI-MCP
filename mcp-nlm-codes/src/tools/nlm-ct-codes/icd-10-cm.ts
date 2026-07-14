// ICD-10-CM diagnosis codes implementation

import { IcdMethodArgs, SearchResponse, CodeResult } from './types.js';
import {
  validateTerms,
  validateMaxList,
  validateOffset,
  validateAndProcessAdditionalQuery,
  makeApiRequest,
} from './utils.js';

export async function searchIcd10Cm(args: IcdMethodArgs): Promise<SearchResponse> {
  // Validate parameters
  const terms = validateTerms(args.terms);
  const maxList = validateMaxList(args.maxList);
  const offset = validateOffset(args.offset);

  // Set defaults for ICD-10-CM
  const searchFields = args.searchFields || 'code,name';
  const displayFields = args.displayFields || 'code,name';

  // Build API URL
  const params = new URLSearchParams({
    terms,
    maxList: maxList.toString(),
    sf: searchFields,
    df: displayFields,
    cf: 'code',
    offset: offset.toString(),
  });

  // Process and validate additionalQuery to handle parentheses issues
  if (args.additionalQuery && typeof args.additionalQuery === 'string') {
    const processedQuery = validateAndProcessAdditionalQuery(args.additionalQuery);
    if (processedQuery !== undefined) {
      params.append('q', processedQuery);
    }
  }

  const apiUrl = `https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?${params.toString()}`;

  try {
    const [totalCount, codes, , displayStrings] = await makeApiRequest(apiUrl);

    // Transform the results into ICD-10-CM format
    const results: CodeResult[] = [];
    if (Array.isArray(codes) && Array.isArray(displayStrings)) {
      for (let i = 0; i < codes.length; i++) {
        const code = codes[i];
        const displayArray = displayStrings[i];

        if (Array.isArray(displayArray) && displayArray.length >= 2) {
          results.push({
            code: displayArray[0], // First element is the code
            name: displayArray[1], // Second element is the name
          });
        } else if (Array.isArray(displayArray) && displayArray.length === 1) {
          results.push({
            code: code,
            name: displayArray[0],
          });
        } else {
          results.push({
            code: code,
            name: code, // Fallback if no description available
          });
        }
      }
    }

    return {
      method: 'icd-10-cm',
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
      throw new Error(`Failed to search ICD-10-CM codes: ${error.message}`);
    }
    throw new Error('Failed to search ICD-10-CM codes: Unknown error');
  }
}
