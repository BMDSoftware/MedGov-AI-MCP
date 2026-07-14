// NPI (National Provider Identifier) Organizations implementation

import { NpiMethodArgs, SearchResponse, CodeResult } from './types.js';
import {
  validateTerms,
  validateMaxList,
  validateOffset,
  validateCount,
  validateAndProcessAdditionalQuery,
  makeApiRequest,
} from './utils.js';

export async function searchNpiOrganizations(args: NpiMethodArgs): Promise<SearchResponse> {
  // Validate parameters
  const terms = validateTerms(args.terms);
  const maxList = validateMaxList(args.maxList);
  const offset = validateOffset(args.offset);
  const count = validateCount(args.count);

  // Set defaults for NPI Organizations
  const searchFields = args.searchFields || 'NPI,name.full,provider_type,addr_practice.full';
  const displayFields = args.displayFields || 'NPI,name.full,provider_type,addr_practice.full';

  // Build API URL
  const params = new URLSearchParams({
    terms,
    maxList: maxList.toString(),
    count: count.toString(),
    offset: offset.toString(),
    sf: searchFields,
    df: displayFields,
    cf: 'NPI',
  });

  // Add optional parameters
  if (args.extraFields && typeof args.extraFields === 'string') {
    params.append('ef', args.extraFields.trim());
  }

  // Process and validate additionalQuery to handle parentheses issues
  const processedQuery = validateAndProcessAdditionalQuery(args.additionalQuery);
  if (processedQuery !== undefined) {
    params.append('q', processedQuery);
  } else if (
    args.additionalQuery &&
    typeof args.additionalQuery === 'string' &&
    args.additionalQuery.trim() === ''
  ) {
    // Handle the specific case of whitespace-only strings that tests expect to be added as empty parameter
    params.append('q', '');
  }

  const apiUrl = `https://clinicaltables.nlm.nih.gov/api/npi_org/v3/search?${params.toString()}`;

  try {
    const [totalCount, codes, extraData, displayStrings] = await makeApiRequest(apiUrl);

    // Transform the results into NPI Organizations format
    const results: CodeResult[] = [];
    if (Array.isArray(codes) && Array.isArray(displayStrings)) {
      for (let i = 0; i < codes.length; i++) {
        const npi = codes[i];
        const displayArray = displayStrings[i];

        const result: CodeResult = {
          code: npi,
          npi: npi,
          // Default display fields mapping
          fullName: Array.isArray(displayArray) && displayArray.length >= 2 ? displayArray[1] : '',
          providerType:
            Array.isArray(displayArray) && displayArray.length >= 3 ? displayArray[2] : '',
          practiceAddress:
            Array.isArray(displayArray) && displayArray.length >= 4 ? displayArray[3] : '',
        };

        // Add extra field data if available
        if (extraData) {
          // Name fields
          if (extraData['name.last']?.[i]) {
            result.lastName = extraData['name.last'][i];
          }
          if (extraData['name.first']?.[i]) {
            result.firstName = extraData['name.first'][i];
          }
          if (extraData['name.middle']?.[i]) {
            result.middleName = extraData['name.middle'][i];
          }
          if (extraData['name.credential']?.[i]) {
            result.credential = extraData['name.credential'][i];
          }
          if (extraData['name.prefix']?.[i]) {
            result.namePrefix = extraData['name.prefix'][i];
          }
          if (extraData['name.suffix']?.[i]) {
            result.nameSuffix = extraData['name.suffix'][i];
          }

          // Practice address fields
          if (extraData['addr_practice.line1']?.[i]) {
            result.practiceAddressLine1 = extraData['addr_practice.line1'][i];
          }
          if (extraData['addr_practice.line2']?.[i]) {
            result.practiceAddressLine2 = extraData['addr_practice.line2'][i];
          }
          if (extraData['addr_practice.city']?.[i]) {
            result.practiceCity = extraData['addr_practice.city'][i];
          }
          if (extraData['addr_practice.state']?.[i]) {
            result.practiceState = extraData['addr_practice.state'][i];
          }
          if (extraData['addr_practice.zip']?.[i]) {
            result.practiceZip = extraData['addr_practice.zip'][i];
          }
          if (extraData['addr_practice.phone']?.[i]) {
            result.practicePhone = extraData['addr_practice.phone'][i];
          }
          if (extraData['addr_practice.fax']?.[i]) {
            result.practiceFax = extraData['addr_practice.fax'][i];
          }
          if (extraData['addr_practice.country']?.[i]) {
            result.practiceCountry = extraData['addr_practice.country'][i];
          }

          // Mailing address fields
          if (extraData['addr_mailing.full']?.[i]) {
            result.mailingAddress = extraData['addr_mailing.full'][i];
          }
          if (extraData['addr_mailing.line1']?.[i]) {
            result.mailingAddressLine1 = extraData['addr_mailing.line1'][i];
          }
          if (extraData['addr_mailing.line2']?.[i]) {
            result.mailingAddressLine2 = extraData['addr_mailing.line2'][i];
          }
          if (extraData['addr_mailing.city']?.[i]) {
            result.mailingCity = extraData['addr_mailing.city'][i];
          }
          if (extraData['addr_mailing.state']?.[i]) {
            result.mailingState = extraData['addr_mailing.state'][i];
          }
          if (extraData['addr_mailing.zip']?.[i]) {
            result.mailingZip = extraData['addr_mailing.zip'][i];
          }
          if (extraData['addr_mailing.phone']?.[i]) {
            result.mailingPhone = extraData['addr_mailing.phone'][i];
          }
          if (extraData['addr_mailing.fax']?.[i]) {
            result.mailingFax = extraData['addr_mailing.fax'][i];
          }
          if (extraData['addr_mailing.country']?.[i]) {
            result.mailingCountry = extraData['addr_mailing.country'][i];
          }

          // Other name fields
          if (extraData['name_other.full']?.[i]) {
            result.otherNameFull = extraData['name_other.full'][i];
          }
          if (extraData['name_other.last']?.[i]) {
            result.otherNameLast = extraData['name_other.last'][i];
          }
          if (extraData['name_other.first']?.[i]) {
            result.otherNameFirst = extraData['name_other.first'][i];
          }
          if (extraData['name_other.middle']?.[i]) {
            result.otherNameMiddle = extraData['name_other.middle'][i];
          }
          if (extraData['name_other.credential']?.[i]) {
            result.otherNameCredential = extraData['name_other.credential'][i];
          }
          if (extraData['name_other.prefix']?.[i]) {
            result.otherNamePrefix = extraData['name_other.prefix'][i];
          }
          if (extraData['name_other.suffix']?.[i]) {
            result.otherNameSuffix = extraData['name_other.suffix'][i];
          }

          // Other IDs (complex structure)
          if (extraData['other_ids']?.[i]) {
            result.otherIds = extraData['other_ids'][i];
          }

          // Licenses (complex structure)
          if (extraData['licenses']?.[i]) {
            result.licenses = extraData['licenses'][i];
          }

          // Authorized official fields
          if (extraData['misc.auth_official.last']?.[i]) {
            result.authorizedOfficialLast = extraData['misc.auth_official.last'][i];
          }
          if (extraData['misc.auth_official.first']?.[i]) {
            result.authorizedOfficialFirst = extraData['misc.auth_official.first'][i];
          }
          if (extraData['misc.auth_official.middle']?.[i]) {
            result.authorizedOfficialMiddle = extraData['misc.auth_official.middle'][i];
          }
          if (extraData['misc.auth_official.credential']?.[i]) {
            result.authorizedOfficialCredential = extraData['misc.auth_official.credential'][i];
          }
          if (extraData['misc.auth_official.title']?.[i]) {
            result.authorizedOfficialTitle = extraData['misc.auth_official.title'][i];
          }
          if (extraData['misc.auth_official.prefix']?.[i]) {
            result.authorizedOfficialPrefix = extraData['misc.auth_official.prefix'][i];
          }
          if (extraData['misc.auth_official.suffix']?.[i]) {
            result.authorizedOfficialSuffix = extraData['misc.auth_official.suffix'][i];
          }
          if (extraData['misc.auth_official.phone']?.[i]) {
            result.authorizedOfficialPhone = extraData['misc.auth_official.phone'][i];
          }

          // Miscellaneous fields
          if (extraData['misc.replacement_NPI']?.[i]) {
            result.replacementNPI = extraData['misc.replacement_NPI'][i];
          }
          if (extraData['misc.EIN']?.[i]) {
            result.ein = extraData['misc.EIN'][i];
          }
          if (extraData['misc.enumeration_date']?.[i]) {
            result.enumerationDate = extraData['misc.enumeration_date'][i];
          }
          if (extraData['misc.last_update_date']?.[i]) {
            result.lastUpdateDate = extraData['misc.last_update_date'][i];
          }
          if (extraData['misc.is_sole_proprietor']?.[i] !== undefined) {
            result.isSoleProprietor = extraData['misc.is_sole_proprietor'][i];
          }
          if (extraData['misc.is_org_subpart']?.[i] !== undefined) {
            result.isOrgSubpart = extraData['misc.is_org_subpart'][i];
          }
          if (extraData['misc.parent_LBN']?.[i]) {
            result.parentLBN = extraData['misc.parent_LBN'][i];
          }
          if (extraData['misc.parent_TIN']?.[i]) {
            result.parentTIN = extraData['misc.parent_TIN'][i];
          }
        }

        results.push(result);
      }
    }

    return {
      method: 'npi-organizations',
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
      throw new Error(`Failed to search NPI Organization records: ${error.message}`);
    }
    throw new Error('Failed to search NPI Organization records: Unknown error');
  }
}
