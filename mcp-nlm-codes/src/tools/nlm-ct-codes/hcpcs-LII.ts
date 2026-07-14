// HCPCS Level II procedure codes implementation

import { HcpcsMethodArgs, SearchResponse, CodeResult } from './types.js';
import {
  validateTerms,
  validateMaxList,
  validateOffset,
  validateCount,
  validateAndProcessAdditionalQuery,
  makeApiRequest,
} from './utils.js';

export async function searchHcpcsLII(args: HcpcsMethodArgs): Promise<SearchResponse> {
  // Validate parameters
  const terms = validateTerms(args.terms);
  const maxList = validateMaxList(args.maxList);
  const offset = validateOffset(args.offset);
  const count = validateCount(args.count);

  // Set defaults for HCPCS
  const searchFields = args.searchFields || 'code,short_desc,long_desc';
  const displayFields = args.displayFields || 'code,display';

  // Build API URL
  const params = new URLSearchParams({
    terms,
    maxList: maxList.toString(),
    count: count.toString(),
    offset: offset.toString(),
    sf: searchFields,
    df: displayFields,
    cf: 'code',
  });

  // Add optional parameters
  if (args.extraFields && typeof args.extraFields === 'string') {
    params.append('ef', args.extraFields.trim());
  }

  // Process and validate additionalQuery to handle parentheses issues
  if (args.additionalQuery && typeof args.additionalQuery === 'string') {
    const processedQuery = validateAndProcessAdditionalQuery(args.additionalQuery);
    if (processedQuery !== undefined) {
      params.append('q', processedQuery);
    }
  }

  const apiUrl = `https://clinicaltables.nlm.nih.gov/api/hcpcs/v3/search?${params.toString()}`;

  try {
    const [totalCount, codes, extraData, displayStrings] = await makeApiRequest(apiUrl);

    // Transform the results into HCPCS format
    const results: CodeResult[] = [];
    if (Array.isArray(codes) && Array.isArray(displayStrings)) {
      for (let i = 0; i < codes.length; i++) {
        const code = codes[i];
        const displayArray = displayStrings[i];

        const result: CodeResult = {
          code: code,
          display:
            Array.isArray(displayArray) && displayArray.length >= 2
              ? displayArray[1]
              : Array.isArray(displayArray) && displayArray.length === 1
                ? displayArray[0]
                : code,
        };

        // Add extra field data if available
        if (extraData) {
          if (extraData.short_desc?.[i]) {
            result.shortDescription = extraData.short_desc[i];
          }
          if (extraData.long_desc?.[i]) {
            result.longDescription = extraData.long_desc[i];
          }
          if (extraData.add_dt?.[i]) {
            result.addDate = extraData.add_dt[i];
          }
          if (extraData.term_dt?.[i]) {
            result.termDate = extraData.term_dt[i];
          }
          if (extraData.act_eff_dt?.[i]) {
            result.actualEffectiveDate = extraData.act_eff_dt[i];
          }
          if (extraData.obsolete?.[i] !== undefined) {
            result.obsolete = extraData.obsolete[i];
          }
          if (extraData.is_noc?.[i] !== undefined) {
            result.isNoc = extraData.is_noc[i];
          }
        }

        results.push(result);
      }
    }

    return {
      method: 'hcpcs-LII',
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
      throw new Error(`Failed to search HCPCS Level II codes: ${error.message}`);
    }
    throw new Error('Failed to search HCPCS Level II codes: Unknown error');
  }
}
