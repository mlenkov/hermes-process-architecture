#!/usr/bin/env python3
"""
Convert human-readable 07.007.md → structured YAML files.

Output: standards/07.007/{meta,otf-a,otf-b,otf-c,otf-d}.yaml
"""

import re, os, sys, textwrap
from collections import OrderedDict


def strip_html_br(text):
    text = text.replace('<br>', '\n').replace('<br/>', '\n')
    # Strip trailing ' |' from markdown table cells
    if text.endswith(' |'):
        text = text[:-2]
    return text.strip()


def parse_markdown(filepath):
    with open(filepath, encoding='utf-8') as f:
        lines = f.readlines()

    # Remove trailing newlines
    lines = [l.rstrip('\n') for l in lines]

    # State: section we're in
    state = 'title'
    sec1_lines = []
    sec2_lines = []
    sec3_lines = []
    sec4_lines = []
    current_sec = None

    title_lines = []
    for line in lines:
        if line.startswith('## I. Общие сведения'):
            current_sec = 'sec1'
            continue
        elif line.startswith('## II.'):
            current_sec = 'sec2'
            continue
        elif line.startswith('## III.'):
            current_sec = 'sec3'
            continue
        elif line.startswith('## IV.'):
            current_sec = 'sec4'
            continue

        if current_sec is None:
            title_lines.append(line)
        elif current_sec == 'sec1':
            # Skip empty lines at start
            sec1_lines.append(line)
        elif current_sec == 'sec2':
            sec2_lines.append(line)
        elif current_sec == 'sec3':
            sec3_lines.append(line)
        elif current_sec == 'sec4':
            sec4_lines.append(line)

    return title_lines, sec1_lines, sec2_lines, sec3_lines, sec4_lines


def parse_title(title_lines):
    """Extract registration metadata from blockquotes."""
    data = {}
    for line in title_lines:
        m = re.match(r'> \*\*Регистрационный номер\*\*:\s*(\S+)', line)
        if m:
            data['reg_number'] = m.group(1).strip()
        m = re.match(r'> \*\*Зарегистрировано в Минюсте РФ\*\*:\s*(.+)', line)
        if m:
            data['minjust_date'] = m.group(1).strip()
            # Extract reg number from this line too
            rm = re.search(r'регистрационный\s*[N№]\s*(\d+)', line)
            if rm:
                data['minjust_number'] = rm.group(1)
        m = re.match(r'> \*\*Утверждён\*\*:\s*(.+)', line)
        if m:
            val = m.group(1).strip()
            om = re.search(r'от\s+(.+?)(?:\s*$)', val)
            if om:
                data['mintrud_order'] = om.group(1).strip()
            else:
                data['mintrud_order'] = val

    m = re.search(r'Профессиональный стандарт "([^"]+)"', ' '.join(title_lines))
    if m:
        data['title'] = m.group(1)

    return data


def parse_sec1(lines):
    """Parse Section I: general info."""
    data = {}
    for line in lines:
        m = re.match(r'- \*\*Вид профессиональной деятельности\*\*:\s*(.+)', line)
        if m:
            data['activity'] = m.group(1).strip()
        m = re.match(r'\s+- \*\*Код\*\*:\s*(.+)', line)
        if m:
            data['code'] = m.group(1).strip()
        m = re.match(r'- \*\*Основная цель\*\*:\s*(.+)', line)
        if m:
            data['purpose'] = m.group(1).strip()
        m = re.match(r'- \*\*ОКЗ\s+(\S+)\*\*:\s*(.+)', line)
        if m:
            data.setdefault('okz', []).append({
                'code': m.group(1),
                'name': m.group(2).strip()
            })
        m = re.match(r'- \*\*ОКВЭД\s+(\S+)\*\*:\s*(.+)', line)
        if m:
            data.setdefault('okved', []).append({
                'code': m.group(1),
                'name': m.group(2).strip()
            })
    return data


def parse_sec4(lines):
    """Parse Section IV: developer info."""
    data = {}
    current = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r'### 4\.1\.\s*(.+)', line)
        if m:
            current = 'resp'
            continue
        m = re.match(r'### 4\.2\.\s*(.+)', line)
        if m:
            current = 'orgs'
            continue
        m = re.match(r'- \*\*Генеральный директор\*\*:\s*(.+)', line)
        if m:
            data['director'] = m.group(1).strip()
            continue
        m = re.match(r'- (.+)', line)
        if m:
            val = m.group(1).strip()
            if current == 'resp':
                data['responsible'] = val
            elif current == 'orgs':
                data.setdefault('organizations', []).append(val)
        m = re.match(r'\d+\.\s*(.+)', line)
        if m and current == 'orgs':
            data.setdefault('organizations', []).append(m.group(1).strip())
    return data


def mk_id(s):
    """Normalize string to node ID: lowercase, only [a-z0-9_]."""
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9_]+', '_', s)
    s = re.sub(r'_+', '_', s)
    s = s.strip('_')
    return s


def parse_kv_table(lines, start_idx):
    """Parse a | | | key-value table starting at start_idx. Returns (data_dict, end_idx)."""
    data = {}
    current_key = None
    current_vals = []
    in_ref_table = False  # ОКЗ/ЕКС/ОКПДТР/ОКСО
    ref_group_key = None
    ref_groups = {}

    i = start_idx
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('| | |') or stripped == '| |':
            # Table boundary
            if current_key:
                if in_ref_table and ref_group_key:
                    ref_groups.setdefault(ref_group_key, []).extend(
                        v for v in current_vals if v
                    )
                    ref_groups[ref_group_key] = ref_groups[ref_group_key]
                elif not in_ref_table:
                    data[current_key] = '\n'.join(current_vals)
                current_vals = []
            current_key = None
            in_ref_table = False
            i += 1
            continue
        if stripped.startswith('|---|---'):
            i += 1
            continue
        if stripped.startswith('| **') and '** |' in stripped:
            # Key-value row: | **key** | value |
            parts = re.findall(r'\*\*(.*?)\*\*\s*\|\s*(.+)', stripped)
            if parts:
                key, val = parts[0]
                key = key.strip()
                val = strip_html_br(val.strip())
                ref_key = key.lower().strip()
                if ref_key in ('окз', 'екс', 'окпдтр', 'оксо'):
                    in_ref_table = True
                    ref_group_key = key
                    ref_groups.setdefault(key, [])
                    if val:
                        ref_groups[key].append(val)
                else:
                    in_ref_table = False
                    if val:
                        data[key] = val
            i += 1
            continue
        if stripped.startswith('| ') and '|' in stripped[2:]:
            # Continuation row: | | value |
            parts = stripped.split('|')
            if len(parts) >= 3:
                first_cell = parts[1].strip()
                second_cell = parts[2].strip() if len(parts) > 2 else ''
                if first_cell.startswith('**') and first_cell.endswith('**'):
                    key = first_cell.strip('* ')
                    val = strip_html_br(second_cell)
                    if key.lower() in ('окз', 'екс', 'окпдтр', 'оксо'):
                        in_ref_table = True
                        ref_group_key = key
                        ref_groups.setdefault(key, [])
                        if val:
                            ref_groups[key].append(val)
                    else:
                        in_ref_table = False
                        if val:
                            data[key] = val
                elif second_cell:
                    val = strip_html_br(second_cell)
                    if in_ref_table and ref_group_key:
                        ref_groups[ref_group_key].append(val)
                    elif current_key:
                        current_vals.append(val)
            i += 1
            continue

        # Stop at headings (ОТФ or ТФ) or list section headers
        if stripped.startswith('###') or stripped.startswith('####'):
            break
        if stripped.startswith('**') and ('**:' in stripped or '** :' in stripped):
            break

        i += 1

    if ref_groups:
        data['references'] = {}
        # Sort: ОКЗ, ЕКС, ОКПДТР, ОКСО
        for rk in ['ОКЗ', 'ЕКС', 'ОКПДТР', 'ОКСО']:
            if rk in ref_groups:
                entries = []
                for e in ref_groups[rk]:
                    parts = e.split(' — ', 1)
                    if len(parts) == 2:
                        entries.append({'code': parts[0], 'name': parts[1]})
                    else:
                        entries.append(e)
                data['references'][rk] = entries

    return data, i


def parse_list_section(lines, start_idx):
    """Parse Трудовые действия/умения/знания lists. Returns (data_dict, end_idx)."""
    data = {}
    current_label = None
    current_items = []

    def save():
        if current_label and current_items:
            key = current_label.lower().replace(' ', '_')
            data[key] = current_items

    i = start_idx
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        # New section: **Label**:
        m = re.match(r'\*\*(.+?)\*\*:', stripped)
        if m:
            save()
            current_label = m.group(1)
            current_items = []
            # Check if there's inline content after the label
            rest = stripped[m.end():].strip()
            if rest and not rest.startswith('-'):
                # Some text after **Label**: - can happen
                pass
            i += 1
            continue
        # List item
        if stripped.startswith('- ') and current_label:
            current_items.append(stripped[2:].strip())
            i += 1
            continue
        # Not a list anymore
        save()
        current_label = None
        current_items = []
        # Don't advance - re-check this line
        break

    save()
    return data, i


def parse_otf_tf(sec3_lines):
    """Parse Section III: extract ОТФ and ТФ blocks."""
    otfs = []
    current_otf = None
    current_tf = None
    i = 0
    lines = sec3_lines

    def save_tf():
        if current_tf and current_otf is not None:
            current_otf['labor_functions'].append(current_tf)

    def save_otf():
        save_tf()
        if current_otf:
            otfs.append(current_otf)

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ОТФ header
        m = re.match(r'### (\d+\.\d+\.\s*Обобщенная трудовая функция)', stripped)
        if m:
            save_otf()
            current_otf = {
                'section': m.group(1).strip(),
                'labor_functions': [],
            }
            current_tf = None
            # Parse ОТФ metadata tables after header
            data, i = parse_kv_table(lines, i + 1)
            current_otf.update(data)
            continue

        # ТФ header
        m = re.match(r'#### (\d+\.\d+\.\d+\.\s*Трудовая функция)', stripped)
        if m:
            save_tf()
            current_tf = {
                'section': m.group(1).strip(),
            }
            # Parse ТФ metadata tables
            data, i = parse_kv_table(lines, i + 1)
            current_tf.update(data)
            continue

        # List sections (Трудовые действия, умения, знания)
        is_list_header = (
            stripped.startswith('**')
            and (stripped.endswith('**:') or stripped.endswith('**'))
            and '**:' in stripped
        )
        if current_tf and is_list_header:
            data, i = parse_list_section(lines, i)
            current_tf.update(data)
            continue

        i += 1

    save_otf()
    return otfs


def extract_name_and_code(data):
    """Extract name and code from parsed table data."""
    name = data.get('Наименование', '')
    code = data.get('Код', '')
    level = data.get('Уровень квалификации', data.get('Уровень (подуровень) квалификации', ''))
    return name, code, level


def build_otf_yaml(otf):
    """Convert parsed ОТФ dict to YAML-friendly OrderedDict."""
    name, code, level = extract_name_and_code(otf)

    y = OrderedDict()
    y['type'] = 'generalized_labor_function'
    y['id'] = f"OTF-{code}" if code else ''
    y['code'] = code
    y['name'] = name
    if level:
        y['qualification_level'] = int(level) if level.isdigit() else level

    origin = otf.get('Происхождение обобщенной трудовой функции', '')
    if origin:
        y['origin'] = [o.strip() for o in origin.split(',')]

    job_titles = otf.get('Возможные наименования должностей, профессий', '')
    if job_titles:
        y['job_titles'] = [jt.strip() for jt in job_titles.split('\n')]

    edu = otf.get('Требования к образованию и обучению', '')
    if edu:
        y['education'] = [e.strip() for e in edu.split('\n') if e.strip()]

    exp = otf.get('Требования к опыту практической работы', '')
    if exp:
        y['experience'] = [e.strip() for e in exp.split('\n') if e.strip()]

    other = otf.get('Другие характеристики', '')
    if other:
        y['other_characteristics'] = [o.strip() for o in other.split('\n') if o.strip()]

    refs = otf.get('references', {})
    if refs:
        y['references'] = refs

    tfs = otf.get('labor_functions', [])
    if tfs:
        y['labor_functions'] = []
        for tf in tfs:
            tf_y = build_tf_yaml(tf)
            if tf_y:
                y['labor_functions'].append(tf_y)

    return y


def build_tf_yaml(tf):
    """Convert parsed ТФ dict to YAML-friendly OrderedDict."""
    name, code, level = extract_name_and_code(tf)
    if not code:
        return None

    y = OrderedDict()
    y['type'] = 'labor_function'
    y['id'] = f"TF-{code.replace('/', '-').replace('.', '-')}"
    y['code'] = code
    y['name'] = name
    if level:
        y['qualification_level'] = int(level) if level.isdigit() else level

    origin = tf.get('Происхождение трудовой функции', '')
    if origin:
        y['origin'] = [o.strip() for o in origin.split(',')]

    for key in ['Трудовые действия', 'Необходимые умения', 'Необходимые знания']:
        items = tf.get(key, [])
        if not items:
            # Try the key with underscores
            alt_key = key.lower().replace(' ', '_')
            items = tf.get(alt_key, [])
        if items:
            y_key = key.lower().replace(' ', '_')
            y[y_key] = items

    return y


def to_yaml_value(obj, indent=0):
    """Custom YAML serializer that outputs clean, AI-friendly YAML.
    Handles OrderedDict, lists, and basic types with proper indentation.
    """
    INDENT = '  '
    prefix = INDENT * indent

    if isinstance(obj, OrderedDict) or isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            # Skip empty values
            if v is None or v == '' or v == [] or v == {}:
                continue
            if isinstance(v, list):
                if all(isinstance(i, str) for i in v):
                    # Simple string list
                    if len(v) == 1 and len(v[0]) < 80:
                        lines.append(f'{prefix}{k}: {v[0]}')
                    else:
                        lines.append(f'{prefix}{k}:')
                        for item in v:
                            lines.append(f'{prefix}- "{escape_yaml(item)}"')
                elif all(isinstance(i, dict) for i in v):
                    # List of dicts — first line inline with '- ', rest indented
                    lines.append(f'{prefix}{k}:')
                    for item in v:
                        inner = to_yaml_value(item, indent + 1)
                        inner_lines = inner.rstrip().split('\n')
                        first = inner_lines[0].lstrip()
                        result = f'{prefix}- {first}'
                        for il in inner_lines[1:]:
                            result += '\n' + prefix + '  ' + il.lstrip()
                        lines.append(result)
                elif all(isinstance(i, OrderedDict) for i in v):
                    lines.append(f'{prefix}{k}:')
                    for item in v:
                        inner = to_yaml_value(item, indent + 1)
                        inner_lines = inner.rstrip().split('\n')
                        first = inner_lines[0].lstrip()
                        result = f'{prefix}- {first}'
                        for il in inner_lines[1:]:
                            result += '\n' + prefix + '  ' + il.lstrip()
                        lines.append(result)
                else:
                    lines.append(f'{prefix}{k}:')
                    for item in v:
                        lines.append(f'{prefix}- {item}')
            elif isinstance(v, dict):
                if all(isinstance(i, str) for i in v.values()):
                    lines.append(f'{prefix}{k}:')
                    for sk, sv in v.items():
                        lines.append(f'{prefix}  {sk}: {sv}')
                else:
                    lines.append(f'{prefix}{k}:')
                    inner = to_yaml_value(v, indent + 1)
                    if inner.strip():
                        lines.append(inner)
            else:
                val_str = str(v)
                if '\n' in val_str:
                    lines.append(f'{prefix}{k}: |')
                    for val_line in val_str.split('\n'):
                        lines.append(f'{prefix}  {val_line}')
                elif len(val_str) > 80 or re.search(r'^\d+[\.]\d+$', val_str) or re.search(r'^\d{2}\.\d{3}$', val_str):
                    lines.append(f'{prefix}{k}: "{escape_yaml(val_str)}"')
                else:
                    lines.append(f'{prefix}{k}: {val_str}')
        return '\n'.join(lines)
    elif isinstance(obj, list):
        lines = []
        for item in obj:
            lines.append(f'{prefix}- {item}')
        return '\n'.join(lines)
    else:
        return f'{prefix}{obj}'


def escape_yaml(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')


def write_yaml_file(filepath, data):
    """Write YAML file with clean formatting."""
    content = to_yaml_value(data)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        f.write('\n')
    print(f"Written {filepath}")


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'standards/07.007.md'
    out_dir = sys.argv[2] if len(sys.argv) > 2 else 'standards/07.007'

    title_lines, sec1_lines, sec2_lines, sec3_lines, sec4_lines = parse_markdown(input_file)

    # Title + meta
    title_data = parse_title(title_lines)
    sec1_data = parse_sec1(sec1_lines)
    sec4_data = parse_sec4(sec4_lines)

    meta = OrderedDict()
    meta['type'] = 'professional_standard'
    meta['code'] = '07.007'
    meta['title'] = title_data.get('title', 'Специалист по процессному управлению')
    meta['registration'] = OrderedDict()
    if 'reg_number' in title_data:
        meta['registration']['reg_number'] = title_data['reg_number']
    if 'minjust_date' in title_data:
        meta['registration']['minjust_date'] = title_data['minjust_date']
    if 'minjust_number' in title_data:
        meta['registration']['minjust_number'] = title_data['minjust_number']
    if 'mintrud_order' in title_data:
        meta['registration']['mintrud_order'] = title_data['mintrud_order']

    meta['general_info'] = OrderedDict()
    if 'activity' in sec1_data:
        meta['general_info']['activity'] = sec1_data['activity']
    if 'purpose' in sec1_data:
        meta['general_info']['purpose'] = sec1_data['purpose']
    if 'okz' in sec1_data:
        meta['general_info']['okz'] = sec1_data['okz']
    if 'okved' in sec1_data:
        meta['general_info']['okved'] = sec1_data['okved']

    if sec4_data:
        meta['developers'] = OrderedDict()
        if 'responsible' in sec4_data:
            meta['developers']['responsible'] = sec4_data['responsible']
        if 'director' in sec4_data:
            meta['developers']['director'] = sec4_data['director']
        if 'organizations' in sec4_data:
            meta['developers']['organizations'] = sec4_data['organizations']

    os.makedirs(out_dir, exist_ok=True)
    write_yaml_file(os.path.join(out_dir, 'meta.yaml'), meta)

    # Parse ОТФ/ТФ
    otfs = parse_otf_tf(sec3_lines)

    # Map ОТФ section to filename
    otf_code_map = {}
    for otf in otfs:
        code = otf.get('code', '')
        if code:
            otf_code_map[code.lower()] = f'otf-{code.lower()}.yaml'
        else:
            # Fallback: use section number
            sec = otf.get('section', '')
            m = re.search(r'(\d+)\.(\d+)', sec)
            if m:
                num = m.group(2)
                otf_code_map[num] = f'otf-unknown-{num}.yaml'

    for otf in otfs:
        code = otf.get('code', '').lower()
        if code:
            filename = f'otf-{code.lower()}.yaml'
        else:
            sec = otf.get('section', '')
            m = re.search(r'(\d+)\.(\d+)', sec)
            filename = f'otf-section-{m.group(2)}.yaml' if m else 'otf-unknown.yaml'
        yaml_data = build_otf_yaml(otf)
        write_yaml_file(os.path.join(out_dir, filename), yaml_data)

    # Summary
    tf_total = sum(len(o.get('labor_functions', [])) for o in otfs)
    print(f"\nDone: {len(otfs)} ОТФ, {tf_total} ТФ → {out_dir}/")


if __name__ == '__main__':
    main()
