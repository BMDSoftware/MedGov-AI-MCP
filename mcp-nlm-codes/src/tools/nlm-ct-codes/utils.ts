// Shared utilities for NLM Clinical Tables API methods

export function validateTerms(terms: any): string {
  if (!terms || typeof terms !== 'string') {
    throw new Error('The "terms" parameter is required and must be a string');
  }
  return terms.trim();
}

export function validateMaxList(maxList: any): number {
  return Math.min(Math.max(maxList || 7, 1), 500);
}

export function validateOffset(offset: any): number {
  return Math.max(offset || 0, 0);
}

export function validateCount(count: any): number {
  return Math.min(Math.max(count || 7, 1), 500);
}

/**
 * Validates and processes additionalQuery parameter to handle known limitations
 * with parentheses in the NLM Clinical Tables API
 */
export function validateAndProcessAdditionalQuery(
  additionalQuery: string | undefined
): string | undefined {
  if (!additionalQuery || typeof additionalQuery !== 'string') {
    return additionalQuery;
  }

  const trimmed = additionalQuery.trim();
  if (!trimmed) {
    return undefined;
  }

  // Check for parentheses grouping which is known to cause issues
  if (hasProblematicParentheses(trimmed)) {
    // Try to transform the query to an equivalent form without parentheses
    const transformed = transformParenthesesQuery(trimmed);

    // Check if this is the OR-AND pattern that already issued its own warning
    const orAndPattern = /^([^()]+)\s+(OR|or)\s+\(([^()]+)\s+(AND|and)\s+([^()]+)\)$/i;
    const isOrAndPattern = orAndPattern.test(trimmed);

    if (transformed !== trimmed) {
      // Only issue the transformation warning if it's not the OR-AND pattern (which has its own warning)
      if (!isOrAndPattern) {
        console.warn(
          `NLM Clinical Tables API Warning: Parentheses grouping detected and transformed.\n` +
            `Original: ${trimmed}\n` +
            `Transformed: ${transformed}\n` +
            `Note: The API has limited support for parentheses in boolean expressions.`
        );
      }
      return transformed;
    } else {
      console.warn(
        `NLM Clinical Tables API Warning: Complex parentheses grouping detected.\n` +
          `Query: ${trimmed}\n` +
          `Note: This query may not work as expected due to API limitations with parentheses.\n` +
          `Consider using simpler boolean expressions without parentheses.`
      );
    }
  }

  return trimmed;
}

/**
 * Checks if the query contains problematic parentheses patterns
 */
function hasProblematicParentheses(query: string): boolean {
  // Check for parentheses that are not part of quoted strings
  const withoutQuotes = query.replace(/"[^"]*"/g, ''); // Remove quoted strings
  return withoutQuotes.includes('(') || withoutQuotes.includes(')');
}

/**
 * Attempts to transform parentheses-based boolean queries into equivalent forms
 * that work better with the NLM Clinical Tables API
 */
function transformParenthesesQuery(query: string): string {
  // Handle common patterns like: field:value AND (field2:value2 OR field3:value3)

  // Pattern 1: A AND (B OR C) -> (A AND B) OR (A AND C) - distribute AND over OR
  const andOrPattern = /^([^()]+)\s+(AND|and)\s+\(([^()]+)\s+(OR|or)\s+([^()]+)\)$/i;
  const andOrMatch = query.match(andOrPattern);
  if (andOrMatch) {
    const [, left, andOp, middle, orOp, right] = andOrMatch;
    return `(${left.trim()} ${andOp} ${middle.trim()}) ${orOp.toUpperCase()} (${left.trim()} ${andOp} ${right.trim()})`;
  }

  // Pattern 2: A OR (B AND C) -> A OR (B AND C) - this might work as multiple separate queries
  const orAndPattern = /^([^()]+)\s+(OR|or)\s+\(([^()]+)\s+(AND|and)\s+([^()]+)\)$/i;
  const orAndMatch = query.match(orAndPattern);
  if (orAndMatch) {
    const [, left, orOp, middle, andOp, right] = orAndMatch;
    // For OR with AND grouping, we can't easily distribute, so suggest separate queries
    console.warn(
      `Complex OR with AND grouping detected. Consider breaking into separate queries:\n` +
        `Query 1: ${left.trim()}\n` +
        `Query 2: ${middle.trim()} ${andOp} ${right.trim()}`
    );
    // Return as-is, but without outer parentheses (don't trigger additional warning)
    return `${left.trim()} ${orOp} ${middle.trim()} ${andOp} ${right.trim()}`;
  }

  // Pattern 3: (A OR B) AND C -> (A AND C) OR (B AND C) - distribute AND over OR
  const orAndPattern2 = /^\(([^()]+)\s+(OR|or)\s+([^()]+)\)\s+(AND|and)\s+([^()]+)$/i;
  const orAndMatch2 = query.match(orAndPattern2);
  if (orAndMatch2) {
    const [, left, orOp, middle, andOp, right] = orAndMatch2;
    return `(${left.trim()} ${andOp} ${right.trim()}) ${orOp.toUpperCase()} (${middle.trim()} ${andOp} ${right.trim()})`;
  }

  // Pattern 4: Simple parentheses removal for basic OR grouping: (A OR B)
  const simpleOrPattern = /^\(([^()]+)\s+(OR|or)\s+([^()]+)\)$/i;
  const simpleOrMatch = query.match(simpleOrPattern);
  if (simpleOrMatch) {
    const [, left, orOp, right] = simpleOrMatch;
    return `${left.trim()} ${orOp} ${right.trim()}`;
  }

  // Pattern 5: Simple parentheses removal for basic AND grouping: (A AND B)
  const simpleAndPattern = /^\(([^()]+)\s+(AND|and)\s+([^()]+)\)$/i;
  const simpleAndMatch = query.match(simpleAndPattern);
  if (simpleAndMatch) {
    const [, left, andOp, right] = simpleAndMatch;
    return `${left.trim()} ${andOp} ${right.trim()}`;
  }

  // If no patterns match, return the original query
  return query;
}

export async function makeApiRequest(url: string): Promise<any> {
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'codes-mcp-server/0.1.2',
    },
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();

  // Parse the API response format: [totalCount, codes, extraData, displayStrings, codeSystems]
  if (!Array.isArray(data) || data.length < 4) {
    throw new Error('Invalid API response format');
  }

  return data;
}
