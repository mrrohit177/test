"""A compact server-side template engine.

Supported syntax (Django-like, deliberately small):
  {{ expr }}                 variable / dotted lookup, optional |filters
  {{ expr | filter:arg }}    filters: upper, lower, title, money, date, default,
                             length, yesno, truncate, safe
  {% if expr %} ... {% elif expr %} ... {% else %} ... {% endif %}
  {% for item in iterable %} ... {% empty %} ... {% endfor %}
  {% include "partial.html" %}
  {% block name %}...{% endblock %}   with {% extends "base.html" %}
  {% url "name" a b %}       reverse a named route
  {% csrf %}                 hidden CSRF input
  {% t "key" %}              translate a UI string
  {# comment #}

Output is HTML-escaped by default; use the |safe filter for trusted HTML.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import settings

_TOKEN_RE = re.compile(r"({%.*?%}|{{.*?}}|{#.*?#})", re.DOTALL)


# --- Filters ----------------------------------------------------------------
def _money(v):
    try:
        return f"₹{float(v):,.2f}".rstrip("0").rstrip(".") if v is not None else ""
    except (ValueError, TypeError):
        return v


def _yesno(v, arg="Yes,No"):
    yes, no = (arg.split(",") + ["Yes", "No"])[:2]
    return yes if v else no


def _truncate(v, n=80):
    s = str(v)
    return s if len(s) <= int(n) else s[: int(n)].rstrip() + "…"


def _date(v, fmt="%d %b %Y"):
    import datetime
    if not v:
        return ""
    if isinstance(v, str):
        for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                v = datetime.datetime.strptime(v[: len(f) + 2].strip(), f)
                break
            except ValueError:
                continue
        else:
            return v
    try:
        return v.strftime(fmt)
    except Exception:
        return str(v)


FILTERS = {
    "upper": lambda v, *a: str(v).upper(),
    "lower": lambda v, *a: str(v).lower(),
    "title": lambda v, *a: str(v).replace("_", " ").title(),
    "capfirst": lambda v, *a: str(v)[:1].upper() + str(v)[1:],
    "money": lambda v, *a: _money(v),
    "length": lambda v, *a: len(v) if v is not None else 0,
    "default": lambda v, *a: v if (v not in (None, "", [])) else (a[0] if a else ""),
    "yesno": lambda v, *a: _yesno(v, a[0] if a else "Yes,No"),
    "truncate": lambda v, *a: _truncate(v, a[0] if a else 80),
    "date": lambda v, *a: _date(v, a[0] if a else "%d %b %Y"),
    "safe": lambda v, *a: SafeString(v),
    "replace_us": lambda v, *a: str(v).replace("_", " "),
}


class SafeString(str):
    """A string that should NOT be auto-escaped."""


# --- Engine -----------------------------------------------------------------
class Template:
    _cache: dict[str, "Template"] = {}

    def __init__(self, source: str, name: str = "<string>"):
        self.source = source
        self.name = name

    @classmethod
    def load(cls, name: str) -> "Template":
        if not settings.DEBUG and name in cls._cache:
            return cls._cache[name]
        path = settings.TEMPLATES_DIR / name
        source = path.read_text(encoding="utf-8")
        tpl = cls(source, name)
        cls._cache[name] = tpl
        return tpl

    def render(self, context: dict[str, Any] | None = None) -> str:
        context = dict(context or {})
        # Walk the full inheritance chain: child -> parent -> grandparent ...
        # Collect each level's blocks; a descendant's block overrides an
        # ancestor's block of the same name. The root ancestor (the template
        # with no {% extends %}) provides the document skeleton that we render.
        chain = []  # [(template, blocks)] from this template up to the root
        current = self
        seen = set()
        while True:
            if current.name in seen:
                break  # guard against cycles
            seen.add(current.name)
            blocks = _collect_blocks(current.source)
            chain.append((current, blocks))
            m = _EXTENDS_RE.search(current.source)
            if not m:
                break
            current = Template.load(m.group(1))

        # Merge blocks: start from root, let descendants override.
        merged: dict[str, str] = {}
        for _tpl, blocks in reversed(chain):
            merged.update(blocks)

        root_template = chain[-1][0]
        body = _strip_extends(root_template.source)
        return _render_nodes(body, context, merged)

    def _render_with_blocks(self, context, child_blocks):
        own_blocks = _collect_blocks(self.source)
        merged = {**own_blocks, **{k: v for k, v in child_blocks.items()}}
        body = _strip_extends(self.source)
        return _render_nodes(body, context, merged)


# --- Parsing helpers --------------------------------------------------------
_EXTENDS_RE = re.compile(r"{%\s*extends\s+['\"](.+?)['\"]\s*%}")
_BLOCK_OPEN_RE = re.compile(r"{%\s*block\s+(\w+)\s*%}")
_BLOCK_CLOSE_RE = re.compile(r"{%\s*endblock\s*%}")


def _strip_extends(src: str) -> str:
    return _EXTENDS_RE.sub("", src)


def _collect_blocks(src: str) -> dict[str, str]:
    """Collect block contents, correctly handling NESTED blocks.

    For a block that itself contains child blocks, the captured content
    includes the child block tags verbatim (they are resolved later during
    node rendering via the merged block map).
    """
    blocks: dict[str, str] = {}
    pos = 0
    length = len(src)
    while pos < length:
        m = _BLOCK_OPEN_RE.search(src, pos)
        if not m:
            break
        name = m.group(1)
        content_start = m.end()
        # walk forward balancing nested block/endblock
        depth = 1
        scan = content_start
        while depth > 0:
            nxt_open = _BLOCK_OPEN_RE.search(src, scan)
            nxt_close = _BLOCK_CLOSE_RE.search(src, scan)
            if not nxt_close:
                # malformed; take the rest
                content_end = length
                scan = length
                depth = 0
                break
            if nxt_open and nxt_open.start() < nxt_close.start():
                depth += 1
                scan = nxt_open.end()
            else:
                depth -= 1
                if depth == 0:
                    content_end = nxt_close.start()
                    scan = nxt_close.end()
                else:
                    scan = nxt_close.end()
        blocks[name] = src[content_start:content_end]
        pos = m.end()  # continue after this block's opening tag so we also
                       # capture nested child blocks as their own entries
    return blocks


def _resolve(expr: str, context: dict) -> Any:
    expr = expr.strip()
    if expr in ("True", "true"):
        return True
    if expr in ("False", "false"):
        return False
    if expr in ("None", "none", "null"):
        return None
    if (expr.startswith('"') and expr.endswith('"')) or (
        expr.startswith("'") and expr.endswith("'")
    ):
        return expr[1:-1]
    try:
        return int(expr)
    except ValueError:
        pass
    try:
        return float(expr)
    except ValueError:
        pass
    # dotted lookup
    parts = expr.split(".")
    val: Any = context.get(parts[0], None)
    for part in parts[1:]:
        if val is None:
            return None
        if isinstance(val, dict):
            val = val.get(part)
        elif isinstance(val, (list, tuple)):
            try:
                val = val[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            val = getattr(val, part, None)
    return val


def _apply_filters(value: Any, filter_str: str, context: dict) -> Any:
    for seg in filter_str.split("|"):
        seg = seg.strip()
        if not seg:
            continue
        if ":" in seg:
            fname, arg = seg.split(":", 1)
            arg = arg.strip()
            # resolve arg (string literal or context var)
            if (arg.startswith('"') and arg.endswith('"')) or (
                arg.startswith("'") and arg.endswith("'")
            ):
                arg = arg[1:-1]
            else:
                resolved = _resolve(arg, context)
                arg = resolved if resolved is not None else arg
            fn = FILTERS.get(fname.strip())
            value = fn(value, arg) if fn else value
        else:
            fn = FILTERS.get(seg)
            value = fn(value) if fn else value
    return value


def _eval_condition(expr: str, context: dict) -> bool:
    expr = expr.strip()
    # support: a == b, a != b, a, not a, a and b, a or b (simple, non-nested)
    for op, func in ((" and ", all), (" or ", any)):
        if op in expr:
            parts = expr.split(op)
            results = [_eval_condition(p, context) for p in parts]
            return func(results)
    if expr.startswith("not "):
        return not _eval_condition(expr[4:], context)
    for op in ("==", "!=", ">=", "<=", ">", "<"):
        if op in expr:
            left, right = expr.split(op, 1)
            lv, rv = _resolve(left.strip(), context), _resolve(right.strip(), context)
            try:
                if op == "==":
                    return lv == rv
                if op == "!=":
                    return lv != rv
                if op == ">":
                    return float(lv) > float(rv)
                if op == "<":
                    return float(lv) < float(rv)
                if op == ">=":
                    return float(lv) >= float(rv)
                if op == "<=":
                    return float(lv) <= float(rv)
            except (TypeError, ValueError):
                return False
    val = _resolve(expr, context)
    if isinstance(val, (list, tuple, dict, str)):
        return len(val) > 0
    return bool(val)


# --- Renderer (token walk) --------------------------------------------------
def _render_nodes(src: str, context: dict, blocks: dict) -> str:
    tokens = _TOKEN_RE.split(src)
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("{{"):
            out.append(_render_var(tok[2:-2], context))
        elif tok.startswith("{#"):
            pass  # comment
        elif tok.startswith("{%"):
            stripped = tok[2:-2].strip()
            keyword = stripped.split()[0] if stripped else ""
            if keyword in ("if",):
                consumed, rendered = _render_if(tokens, i, context, blocks)
                out.append(rendered)
                i = consumed
                continue
            elif keyword == "for":
                consumed, rendered = _render_for(tokens, i, context, blocks)
                out.append(rendered)
                i = consumed
                continue
            elif keyword == "block":
                name = stripped.split()[1]
                consumed = _find_end(tokens, i, "block", "endblock")
                block_src = blocks.get(name)
                if block_src is None:
                    block_src = _slice(tokens, i + 1, consumed)
                out.append(_render_nodes(block_src, context, blocks))
                i = consumed + 1
                continue
            elif keyword == "include":
                name = stripped.split(None, 1)[1].strip().strip("'\"")
                out.append(Template.load(name)._render_with_blocks(context, blocks))
            elif keyword == "url":
                out.append(_render_url(stripped, context))
            elif keyword == "csrf":
                token = context.get("csrf_token", "")
                out.append(
                    f'<input type="hidden" name="csrf_token" value="{html.escape(token)}">'
                )
            elif keyword == "t":
                out.append(_render_translate(stripped, context))
        else:
            out.append(tok)
        i += 1
    return "".join(out)


def _render_var(expr: str, context: dict) -> str:
    if "|" in expr:
        base, filters = expr.split("|", 1)
        value = _resolve(base, context)
        value = _apply_filters(value, filters, context)
    else:
        value = _resolve(expr, context)
    if value is None:
        return ""
    if isinstance(value, SafeString):
        return str(value)
    return html.escape(str(value))


def _render_url(stripped: str, context: dict) -> str:
    from core.routing import router
    parts = stripped.split()[1:]
    name = parts[0].strip("'\"")
    args = [str(_resolve(p, context) if not (p.startswith(("'", '"'))) else p.strip("'\"")) for p in parts[1:]]
    try:
        # positional args map onto <param> order
        pattern = router._by_name.get(name, "")
        import re as _re
        param_names = _re.findall(r"<(\w+)>", pattern)
        kwargs = dict(zip(param_names, args))
        return html.escape(router.url(name, **kwargs))
    except Exception:
        return "#"


def _render_translate(stripped: str, context: dict) -> str:
    from core.i18n import translate
    parts = stripped.split(None, 1)
    key = parts[1].strip().strip("'\"") if len(parts) > 1 else ""
    lang = context.get("lang", settings.DEFAULT_LANGUAGE)
    return html.escape(translate(key, lang))


def _render_if(tokens, start, context, blocks):
    depth = 0
    branches = []  # (condition_or_None, [token slice])
    current_cond = tokens[start][2:-2].strip()[3:].strip()  # after 'if '
    current_body_start = start + 1
    i = start + 1
    else_cond = None
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("{%"):
            kw = tok[2:-2].strip().split()[0]
            inner = tok[2:-2].strip()
            if kw == "if":
                depth += 1
            elif kw == "endif":
                if depth == 0:
                    branches.append((current_cond, _slice(tokens, current_body_start, i)))
                    break
                depth -= 1
            elif kw in ("elif", "else") and depth == 0:
                branches.append((current_cond, _slice(tokens, current_body_start, i)))
                current_cond = None if kw == "else" else inner[5:].strip()
                current_body_start = i + 1
        i += 1
    for cond, body in branches:
        if cond is None or _eval_condition(cond, context):
            return i + 1, _render_nodes(body, context, blocks)
    return i + 1, ""


def _render_for(tokens, start, context, blocks):
    header = tokens[start][2:-2].strip()  # for x in items
    m = re.match(r"for\s+(\w+)\s+in\s+(.+)", header)
    var_name, iter_expr = m.group(1), m.group(2).strip()
    end = _find_end(tokens, start, "for", "endfor")
    # find optional {% empty %}
    body_tokens, empty_tokens = [], []
    depth = 0
    i = start + 1
    target = body_tokens
    while i < end:
        tok = tokens[i]
        if tok.startswith("{%"):
            kw = tok[2:-2].strip().split()[0]
            if kw == "for":
                depth += 1
            elif kw == "endfor":
                depth -= 1
            elif kw == "empty" and depth == 0:
                target = empty_tokens
                i += 1
                continue
        target.append(tok)
        i += 1
    body_src = "".join(body_tokens)
    items = _resolve(iter_expr, context)
    out = []
    if items:
        seq = list(items)
        total = len(seq)
        for idx, item in enumerate(seq):
            loop_ctx = dict(context)
            loop_ctx[var_name] = item
            loop_ctx["forloop"] = {
                "index": idx + 1, "index0": idx, "first": idx == 0,
                "last": idx == total - 1, "counter": idx + 1,
            }
            out.append(_render_nodes(body_src, loop_ctx, blocks))
    else:
        out.append(_render_nodes("".join(empty_tokens), context, blocks))
    return end + 1, "".join(out)


def _find_end(tokens, start, open_kw, close_kw):
    depth = 0
    i = start + 1
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("{%"):
            kw = tok[2:-2].strip().split()[0]
            if kw == open_kw:
                depth += 1
            elif kw == close_kw:
                if depth == 0:
                    return i
                depth -= 1
        i += 1
    return len(tokens) - 1


def _slice(tokens, start, end):
    return "".join(tokens[start:end])


def render_to_string(template_name: str, context: dict | None = None) -> str:
    return Template.load(template_name).render(context or {})
