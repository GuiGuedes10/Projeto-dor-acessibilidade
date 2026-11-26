"""Consultas Cypher; valores são enviados separadamente como parâmetros."""

SEARCH_STOPWORDS = {
    'a', 'o', 'os', 'as', 'de', 'da', 'do', 'das', 'dos', 'em', 'e',
    'que', 'no', 'na', 'tem', 'como', 'para', 'puc',
}
DIACRITICS = [
    ['á', 'a'], ['à', 'a'], ['ã', 'a'], ['â', 'a'], ['é', 'e'], ['ê', 'e'],
    ['í', 'i'], ['ó', 'o'], ['ô', 'o'], ['õ', 'o'], ['ú', 'u'], ['ç', 'c'],
]


def projection(schema, alias='p'):
    text = f'coalesce({alias}.{schema.text}, "")' if schema.text else '""'
    return f'''{alias}.{schema.url} AS url,
coalesce({alias}.{schema.title}, "") AS title,
{alias}.{schema.restricted} AS restricted,
CASE WHEN {alias}.{schema.restricted} = true THEN ""
     ELSE substring({text}, 0, $content_limit) END AS text,
CASE WHEN {alias}.{schema.restricted} = true THEN ""
     ELSE substring(coalesce({alias}.{schema.html}, ""), 0, $html_limit) END AS html'''


def read_page_query(schema):
    return f'''MATCH (p:{schema.label})
WHERE p.{schema.url} IN $urls
RETURN {projection(schema)}
ORDER BY CASE WHEN p.{schema.url} = $requested_url THEN 0 ELSE 1 END, url
LIMIT 1'''


def search_pages_query(schema):
    text = f'coalesce(p.{schema.text}, "")' if schema.text else '""'
    return f'''MATCH (p:{schema.label})
WITH p, reduce(t = toLower(coalesce(p.{schema.title}, '') + ' ' + coalesce(p.{schema.url}, '') + ' ' +
    CASE WHEN p.{schema.restricted} = true THEN '' ELSE
    substring({text}, 0, 20000) + ' ' + substring(coalesce(p.{schema.html}, ''), 0, 20000) END),
    pair IN $pairs | replace(t, pair[0], pair[1])) AS searchable
WITH p, [term IN $terms WHERE searchable CONTAINS
    reduce(t = term, pair IN $pairs | replace(t, pair[0], pair[1]))] AS hits
WHERE size(hits) > 0
RETURN {projection(schema)}, size(hits) AS score
ORDER BY score DESC, url ASC LIMIT $limit'''


def outgoing_links_query(schema):
    link_text = f'coalesce(r.{schema.link_text}, "")' if schema.link_text else '""'
    return f'''MATCH (p:{schema.label})-[r:{schema.relation}]->(dest:{schema.label})
WHERE p.{schema.url} IN $urls
RETURN DISTINCT dest.{schema.url} AS url,
    coalesce(dest.{schema.title}, '') AS title,
    dest.{schema.restricted} AS restricted, {link_text} AS link_text
ORDER BY url LIMIT $limit'''


def navigation_path_query(schema, max_hops):
    link_text = f'coalesce(rel.{schema.link_text}, "")' if schema.link_text else '""'
    return f'''MATCH (start:{schema.label}), (target:{schema.label})
WHERE start.{schema.url} IN $start_urls AND target.{schema.url} IN $target_urls
MATCH path = shortestPath((start)-[:{schema.relation}*1..{max_hops}]->(target))
RETURN [node IN nodes(path) | {{url: node.{schema.url},
    title: coalesce(node.{schema.title}, ''), restricted: node.{schema.restricted}}}] AS pages,
    [rel IN relationships(path) | {link_text}] AS link_texts, length(path) AS click_count
ORDER BY click_count ASC LIMIT 1'''
