"""提取每个端点的核心业务 token (查询条件/ORM 模型/错误码/副作用) 供 diff。"""
import ast
import re
from pathlib import Path


def normalize_path(p: str) -> str:
    return re.sub(r'\{(\w+)\}', r':\1', p).rstrip('/') or '/'


def find_endpoint_functions(file_text: str) -> dict[str, dict]:
    out = {}
    tree = ast.parse(file_text)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr in {'get', 'post', 'put', 'patch', 'delete'}
            ):
                method = func.attr.upper()
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    path = dec.args[0].value
                    tokens = extract_body_tokens(node)
                    out[f'{method} {normalize_path(path)}'] = {
                        'func': node.name,
                        'tokens': tokens,
                    }
    return out


def extract_body_tokens(fn) -> list[str]:
    tokens = []
    for stmt in ast.walk(fn):
        if isinstance(stmt, ast.Call):
            name = ast.unparse(stmt.func)
            args = []
            for a in stmt.args:
                if isinstance(a, ast.Constant):
                    args.append(repr(a.value))
                elif isinstance(a, ast.Name):
                    args.append(a.id)
                elif isinstance(a, ast.Attribute):
                    args.append(ast.unparse(a))
            tokens.append(f'{name}({", ".join(args[:3])})')
        elif isinstance(stmt, ast.Constant) and isinstance(stmt.value, str):
            if 'TODO' in stmt.value or 'FIXME' in stmt.value:
                tokens.append(f'# {stmt.value[:80]}')
    return tokens[:30]


def collect_tokens(router_dir: Path) -> dict[str, list[str]]:
    all_tokens: dict[str, list[str]] = {}
    for f in sorted(router_dir.glob('*.py')):
        try:
            text = f.read_text(encoding='utf-8')
        except Exception:
            continue
        try:
            eps = find_endpoint_functions(text)
        except SyntaxError:
            continue
        for k, v in eps.items():
            key = f'{k}  # {f.stem}.{v["func"]}'
            all_tokens[key] = v['tokens']
    return all_tokens


n = collect_tokens(Path('new/services/api/src/executive_ai_api/routers'))
b = collect_tokens(Path('backend/src/api/routers'))


def parse_key(s: str) -> tuple[str, str]:
    parts = s.split('  # ')
    return parts[0], parts[1] if len(parts) > 1 else ''


n_keys = {parse_key(k)[0]: parse_key(k)[1] for k in n}
b_keys = {parse_key(k)[0]: parse_key(k)[1] for k in b}

common = set(n_keys) & set(b_keys)
print(f'\n=== Common endpoints: {len(common)} ===\n')

# 简化：输出每个共有端点，仅展示 token 的集合差异
for path in sorted(common):
    n_tok = n[f'{path}  # {n_keys[path]}']
    b_tok = b[f'{path}  # {b_keys[path]}']
    if set(n_tok) == set(b_tok):
        continue
    print(f'\n[{path}]')
    print(f'  new: {n_keys[path]}')
    for t in n_tok[:20]:
        print(f'    + {t}')
    print(f'  be:  {b_keys[path]}')
    for t in b_tok[:20]:
        print(f'    + {t}')