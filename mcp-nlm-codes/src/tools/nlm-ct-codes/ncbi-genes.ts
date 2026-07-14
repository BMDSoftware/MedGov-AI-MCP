import { CodeResult, NcbiGenesMethodArgs, SearchResponse } from './types.js';
import { makeApiRequest, validateMaxList, validateOffset, validateTerms } from './utils.js';

/**
 * Search NCBI Genes
 * Provides access to information about human genes from NCBI's Gene dataset
 * Includes gene symbols, descriptions, chromosomal locations, and cross-references
 */
export async function searchNcbiGenes(args: NcbiGenesMethodArgs): Promise<SearchResponse> {
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

  // Set defaults for NCBI Genes
  const finalSearchFields =
    searchFields ||
    'GeneID,Symbol,Synonyms,description,chromosome,map_location,type_of_gene,HGNC_ID,dbXrefs';
  const finalDisplayFields =
    displayFields || '_code_system,_code,chromosome,Symbol,description,type_of_gene';
  const finalCodeField = codeField || 'GeneID';

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

  const url = `https://clinicaltables.nlm.nih.gov/api/ncbi_genes/v3/search?${params.toString()}`;

  try {
    const response = await makeApiRequest(url);

    // NCBI Genes API returns array format: [total, codes, extraData, displayData, codeSystems]
    if (!Array.isArray(response) || response.length < 4) {
      throw new Error('Invalid response format from NCBI Genes API');
    }

    const [totalCount, codes, extraData, displayData] = response;

    if (!Array.isArray(codes) || !Array.isArray(displayData)) {
      throw new Error('Invalid response structure from NCBI Genes API');
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
      method: 'ncbi-genes',
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
      throw new Error(`Failed to search NCBI Genes: ${error.message}`);
    }
    throw new Error('Failed to search NCBI Genes: Unknown error');
  }
}
