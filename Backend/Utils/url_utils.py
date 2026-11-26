"""Validação e normalização de URLs HTTP, com filtro opcional de domínio."""
from urllib.parse import urlsplit, urlunsplit


def clean_url(value, *, keep_fragment=False, allowed_domains=None):
    parts = urlsplit(value.strip())
    if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password:
        raise ValueError('Informe uma URL HTTP ou HTTPS válida, sem credenciais.')
    domains = [item.strip().lower() for item in (allowed_domains or []) if item.strip()]
    host = parts.hostname.lower()
    if allowed_domains is not None and not any(host == domain or host.endswith('.' + domain) for domain in domains):
        raise ValueError('A URL não pertence aos domínios permitidos.')
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or '/', parts.query,
                       parts.fragment if keep_fragment else ''))
