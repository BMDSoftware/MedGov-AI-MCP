import { CodeResult, LoincQuestionsMethodArgs, SearchResponse } from './types.js';
import { makeApiRequest, validateMaxList, validateOffset, validateTerms } from './utils.js';

/**
 * Search LOINC Questions and Forms
 * LOINC is a universal code system for medical tests and measurements
 * Provides access to questions, forms, and their definitions with answer lists
 */
export async function searchLoincQuestions(
  args: LoincQuestionsMethodArgs
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
    type,
    available,
    excludeCopyrighted,
  } = args;

  // Set defaults for LOINC Questions
  const finalSearchFields =
    searchFields ||
    'text,COMPONENT,CONSUMER_NAME,RELATEDNAMES2,METHOD_TYP,SHORTNAME,LONG_COMMON_NAME,LOINC_NUM';
  const finalDisplayFields = displayFields || 'text';
  const finalCodeField = codeField || 'LOINC_NUM';

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
  if (excludeCopyrighted !== undefined)
    params.append('excludeCopyrighted', excludeCopyrighted.toString());

  // Build base URL based on type
  const baseUrl = 'https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search';

  if (type) {
    if (type === 'question') {
      params.append('type', 'question');
    } else if (type === 'form') {
      params.append('type', 'form');
      if (available !== undefined) {
        params.append('available', available.toString());
      }
    } else if (type === 'form_and_section') {
      params.append('type', 'form_and_section');
      if (available !== undefined) {
        params.append('available', available.toString());
      }
    } else if (type === 'panel') {
      params.append('type', 'panel');
    }
  }

  const url = `${baseUrl}?${params.toString()}`;

  try {
    const response = await makeApiRequest(url);

    // LOINC API returns array format: [total, codes, extraData, displayData, codeSystems]
    if (!Array.isArray(response) || response.length < 4) {
      throw new Error('Invalid response format from LOINC Questions API');
    }

    const [totalCount, codes, extraData, displayData] = response;

    if (!Array.isArray(codes) || !Array.isArray(displayData)) {
      throw new Error('Invalid response structure from LOINC Questions API');
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
      method: 'loinc-questions',
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
      throw new Error(`Failed to search LOINC Questions: ${error.message}`);
    }
    throw new Error('Failed to search LOINC Questions: Unknown error');
  }
}
