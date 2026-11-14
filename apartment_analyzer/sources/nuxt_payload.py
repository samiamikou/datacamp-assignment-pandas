"""Decode the ``__NUXT_DATA__`` payload embedded in Nuxt 3 pages."""

import json

WRAPPERS = ("ShallowReactive", "Reactive", "Ref", "ShallowRef",
            "EmptyRef", "EmptyShallowRef", "NuxtError")
SPECIAL = ("Date", "Set", "Map", "BigInt", "RegExp")


def _is_tagged(value, tags):
    return bool(value) and isinstance(value[0], str) and value[0] in tags


def load(html):
    """Return the decoded payload of a Nuxt page, or None if absent."""
    marker = html.find('id="__NUXT_DATA__"')
    if marker < 0:
        return None
    start = html.find(">", marker) + 1
    raw = json.loads(html[start:html.find("</script>", start)])
    memo = {}

    def resolve(idx):
        if idx in memo:
            return memo[idx]
        value = raw[idx]
        if isinstance(value, dict):
            out = memo[idx] = {}
            out.update({k: resolve(v) for k, v in value.items()})
            return out
        if isinstance(value, list):
            if _is_tagged(value, WRAPPERS):
                out = resolve(value[1]) if len(value) > 1 else None
            elif _is_tagged(value, SPECIAL):
                out = value[1] if len(value) > 1 else None
            else:
                out = memo[idx] = []
                out.extend(resolve(v) for v in value)
                return out
            memo[idx] = out
            return out
        memo[idx] = value
        return value

    return resolve(0)
