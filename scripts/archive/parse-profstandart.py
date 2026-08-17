#!/usr/bin/env python3
"""
Parse professional standard from classinform.ru HTML to clean Markdown.

Usage:
    python3 parse-profstandart.py --url <URL> --output <FILE>
    python3 parse-profstandart.py --file <HTML_FILE> --output <MARKDOWN_FILE>
"""

import re, sys, argparse, os
from html import unescape

try:
    from lxml import html as lxml_html
except ImportError:
    lxml_html = None


# ── helpers ──────────────────────────────────────────────────────────────────

def strip_html(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    text = re.sub(r'(\w)-\s+(\w)', r'\1-\2', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def text_from_td(td_html):
    texts = []
    for div in re.finditer(r'<div[^>]*>(.*?)</div>', td_html, re.DOTALL):
        t = strip_html(div.group(1))
        if t:
            texts.append(t)
    if texts:
        return ' '.join(texts)
    t = strip_html(td_html)
    return t if t else ''


def extract_table_rows(table_html, min_text_len=1):
    rows = []
    for tr_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL):
        cells = []
        for td_match in re.finditer(r'<t[dh][^>]*>(.*?)</t[dh]>', tr_match.group(1), re.DOTALL):
            text = text_from_td(td_match.group(1))
            cells.append(text)
        if cells and any(len(c) >= min_text_len for c in cells):
            rows.append(cells)
    return rows


def raw_text(html):
    """Strip all tags from html block."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html)).strip()


# ── table formatters ─────────────────────────────────────────────────────────

def fmt_table(rows, header=None):
    """Render a 2-column Markdown table from key-value pairs.
    Each row is [key, value].  Returns '' if no rows.
    """
    data = list(rows) if rows else []
    if not data:
        return ''
    out = ['| | |', '|---|---|']
    if header:
        out.insert(0, f'| **{header[0]}** | {header[1]} |')
    for row in data:
        if not row:
            continue
        cells = [c for c in row if c and c not in ('X', '', '-')]
        if len(cells) >= 2:
            val = ' '.join(cells[1:])
            out.append(f'| **{cells[0]}** | {val} |')
        elif len(cells) == 1:
            out.append(f'| | {cells[0]} |')
    if len(out) <= 2:
        return ''
    return '\n'.join(out)


def format_header_table(rows):
    named = {}
    for row in rows:
        for i in range(0, len(row) - 1, 2):
            k = row[i].strip().rstrip(':') if row[i] else ''
            v = row[i + 1] if i + 1 < len(row) else ''
            if k:
                named[k] = v
    pairs = [(k, named[k]) for k in named]
    return fmt_table(pairs)


def format_origin_table(rows):
    out = ['| | |', '|---|---|']
    has_data = False
    for row in rows:
        cells = [c for c in row if c and c not in ('', '-')]
        if len(cells) >= 2:
            label = cells[0]
            vals = [c for c in cells[1:] if c != 'X']
            if vals:
                out.append(f'| **{label}** | {", ".join(vals)} |')
                has_data = True
    return '\n'.join(out) if has_data else ''


def format_list_table(rows):
    list_labels = {
        'трудовые действия', 'необходимые умения', 'необходимые знания',
        'другие характеристики'
    }
    sections = []
    current_label = None
    current_items = []

    for row in rows:
        if not row:
            continue
        first = row[0].strip().lower() if row[0] else ''
        if first in list_labels:
            if current_label:
                sections.append((current_label, current_items))
                current_items = []
            current_label = row[0].strip()
            if len(row) >= 2 and row[1].strip() and row[1].strip() != '-':
                current_items.append(row[1].strip())
        elif current_label:
            if len(row) >= 2 and row[1].strip() and row[1].strip() != '-':
                current_items.append(row[1].strip())
            elif len(row) == 1 and row[0].strip() and row[0].strip() != '-':
                current_items.append(row[0].strip())

    if current_label:
        sections.append((current_label, current_items))

    out = []
    for label, items in sections:
        if not items:
            continue
        out.append(f'**{label}**:')
        for item in items:
            out.append(f'  - {item}')
    return '\n'.join(out)


REFERENCE_GROUP_HEADERS = {'окз', 'екс', 'окпдтр', 'оксо'}

def format_reference_table(rows):
    out = ['| | |', '|---|---|']
    for row in rows:
        first = row[0].strip().lower() if row[0] else ''
        # Skip header row ("Наименование документа | Код | Наименование...")
        if first == 'наименование документа':
            continue
        if first in REFERENCE_GROUP_HEADERS:
            label = row[0].strip()
            code = row[1] if len(row) > 1 and row[1] and row[1] != '-' else ''
            name = row[2] if len(row) > 2 and row[2] else ''
            entry = f'{code} — {name}' if code and name else (name or code)
            out.append(f'| **{label}** | {entry} |')
        else:
            code = row[1] if len(row) > 1 and row[1] and row[1] != '-' else ''
            name = row[2] if len(row) > 2 and row[2] else ''
            entry = f'{code} — {name}' if code and name else (name or code)
            if entry and entry != '-':
                out.append(f'| | {entry} |')
    if len(out) <= 2:
        return ''
    return '\n'.join(out)


def format_education_table(rows):
    pairs = []
    for row in rows:
        if len(row) >= 2 and row[0]:
            key = row[0].rstrip(':')
            val = row[1] if row[1] and row[1] != '-' else ''
            if val:
                pairs.append((key, val))
    if not pairs:
        return ''
    out = ['| | |', '|---|---|']
    for k, v in pairs:
        v_md = v.replace(' или ', '<br>или ')
        out.append(f'| **{k}** | {v_md} |')
    return '\n'.join(out)


def classify_and_format_table(rows):
    if not rows:
        return ''

    first_cell = rows[0][0].strip().lower() if rows[0] else ''

    if first_cell in ('трудовые действия', 'необходимые умения', 'необходимые знания',
                       'другие характеристики'):
        return format_list_table(rows)

    if first_cell == 'наименование' and len(rows[0]) >= 4:
        return format_header_table(rows)

    if first_cell in ('происхождение трудовой функции',
                       'происхождение обобщенной трудовой функции'):
        return format_origin_table(rows)

    if first_cell in REFERENCE_GROUP_HEADERS:
        return format_reference_table(rows)

    if first_cell in ('возможные наименования должностей, профессий',
                       'возможные наименования должностей'):
        return format_education_table(rows)

    if first_cell == 'наименование документа':
        return format_reference_table(rows)

    if len(rows) <= 3 and all(len(r) <= 4 for r in rows):
        lines = []
        for row in rows:
            non_empty = [c for c in row if c and c not in ('X', '', '-')]
            if len(non_empty) == 2:
                lines.append(f'- **{non_empty[0]}**: {non_empty[1]}')
            elif non_empty:
                lines.append(f'- {", ".join(non_empty)}')
        return '\n'.join(lines)

    lines = []
    for row in rows:
        non_empty = [c for c in row if c and c not in ('X', '', '-')]
        if len(non_empty) == 2:
            lines.append(f'- **{non_empty[0]}**: {non_empty[1]}')
        elif non_empty:
            lines.append(f'- {", ".join(non_empty)}')
    return '\n'.join(lines)


# ── Section I formatters ────────────────────────────────────────────────────

def format_sec1_activity_table(rows):
    """Table 1: Main activity name + code.
    Row 0 has data ['Деятельность...', '', '07.007'].
    Row 1 has labels ['(наименование...)', '', 'Код'] — suppress it.
    """
    data_rows = [r for r in rows if not any('(наименование' in c.lower() for c in r)]
    if not data_rows:
        data_rows = rows[:1]

    out = []
    for row in data_rows:
        non_empty = [c for c in row if c and c not in ('X', '', '-')]
        if len(non_empty) >= 2:
            name = non_empty[0]
            code = non_empty[-1]
            out.append(f'- **Вид профессиональной деятельности**: {name}')
            out.append(f'  - **Код**: {code}')
        elif non_empty:
            out.append(f'- {", ".join(non_empty)}')
    return '\n'.join(out)


def format_sec1_purpose_table(rows):
    """Table 2: Single-cell purpose statement."""
    for row in rows:
        cells = [c for c in row if c and c not in ('X', '', '-')]
        if cells:
            return f'- **Основная цель**: {cells[0]}'
    return ''


def format_sec1_okz_table(rows):
    """Table 3: OKZ codes with two groups (code + name) in one row."""
    if len(rows) < 2:
        return ''
    out = []
    for row in rows:
        non_empty = [c for c in row if c and c not in ('X', '', '-')]
        # Row 0 has data, row 1 has labels
        if len(non_empty) >= 4 and all('код' in c.lower() or '(' in c for c in non_empty):
            continue  # skip label row
        if len(non_empty) >= 4:
            out.append(f'- **ОКЗ {non_empty[0]}**: {non_empty[1]}')
            out.append(f'- **ОКЗ {non_empty[2]}**: {non_empty[3]}')
        elif len(non_empty) == 2:
            out.append(f'- **ОКЗ**: {non_empty[0]} — {non_empty[1]}')
    return '\n'.join(out) if out else classify_and_format_table(rows)


def format_sec1_okved_table(rows):
    """Table 4: OKVED (single group, code + name)."""
    if len(rows) < 2:
        return ''
    out = []
    for row in rows:
        non_empty = [c for c in row if c and c not in ('X', '', '-')]
        if any('код' in c.lower() or '(' in c for c in non_empty):
            continue
        if len(non_empty) >= 2:
            out.append(f'- **ОКВЭД {non_empty[0]}**: {non_empty[1]}')
        elif non_empty:
            out.append(f'- **ОКВЭД**: {", ".join(non_empty)}')
    return '\n'.join(out) if out else classify_and_format_table(rows)


# ── Title block formatter ────────────────────────────────────────────────────

def format_title_block(html_block):
    """
    Extract structured title info from HTML block before Section I.
    Strips navigation breadcrumbs, search form.
    """
    text = raw_text(html_block)

    lines = []

    # Registration number
    m = re.search(r'регистрационный\s*[N№]\s*(\d+)', text)
    reg_num = m.group(1) if m else ''

    # Registration date
    m = re.search(r'(\d+\s+\S+\s+\d{4}\s*года)', text)
    reg_date = m.group(1) if m else ''

    # Approval order
    m = re.search(r'приказом\s+Министерства.*?от\s+(\d+\s+\S+\s+\d{4}\s*года\s*[N№]\s*\d+[а-я]*)', text, re.DOTALL)
    order = m.group(1) if m else ''
    order = re.sub(r'\s+', ' ', order).strip()

    # Registration number table
    m = re.search(r'(\d+)\s*Регистрационный номер', text)
    reg_table_num = m.group(1) if m else ''

    lines.append(f'> **Регистрационный номер**: {reg_table_num or reg_num}')
    if reg_date:
        lines.append(f'> **Зарегистрировано в Минюсте РФ**: {reg_date}')
    if order:
        lines.append(f'> **Утверждён**: Приказом Минтруда России от {order}')
    lines.append('')
    lines.append(f'# Профессиональный стандарт "Специалист по процессному управлению"')
    lines.append('')

    return '\n'.join(lines)


# ── Section IV formatter ─────────────────────────────────────────────────────

def format_developer_table(rows):
    """Format developer info tables.
    Section 4.1: single-cell org name + key-value for director info.
    Section 4.2: numbered list (col 1 = number, col 2 = org name).
    """
    out = []
    for row in rows:
        non_empty = [c for c in row if c and c not in ('X', '', '-')]
        if len(non_empty) >= 2 and non_empty[0].strip().isdigit():
            # Numbered list item (4.2)
            out.append(f'{non_empty[0]}. {non_empty[1]}')
        elif len(non_empty) == 2:
            out.append(f'- **{non_empty[0]}**: {non_empty[1]}')
        elif len(non_empty) == 1:
            out.append(f'- {non_empty[0]}')
    return '\n'.join(out)


# ── main parser ──────────────────────────────────────────────────────────────

def merge_rowspan_rows(rows):
    """
    In the functional map table (Section II), rowspan in cols 0-2 leaves
    continuation rows with empty cols 0-2. Merge them:

    Track active values for cols 0-2. When a continuation row has text in
    col 1, it's a word-split (e.g. "процессной"+"архитектуры") — merge into
    active col 1. Then fill cols 0-2 of continuation row from active values
    and keep it as a separate data row (cols 3-5 are new ТФ data, not
    continuation of previous).

    After merge, backtrack to fill all rows in the same ОТФ group with the
    final merged col 1, so the first row also gets the complete name.
    """
    if not rows:
        return rows

    merged = []
    active = ['', '', '']
    group_start = 0

    for row in rows:
        new_row = list(row)
        while len(new_row) < 3:
            new_row.append('')

        is_continuation = (not row[0] or row[0] == '-')

        if is_continuation:
            if len(row) > 1 and row[1] and row[1] != '-':
                if active[1] and not active[1].endswith(' '):
                    active[1] += ' '
                active[1] += row[1]
            new_row[0] = active[0]
            new_row[1] = active[1]
            new_row[2] = active[2]
        else:
            active[0] = row[0] if row[0] else ''
            active[1] = row[1] if len(row) > 1 and row[1] else ''
            active[2] = row[2] if len(row) > 2 and row[2] else ''
            group_start = len(merged)

        merged.append(new_row)

    # Backtrack: propagate final col 1 to all rows in the same ОТФ group
    i = len(merged) - 1
    while i >= 0:
        if merged[i][0]:
            group_col1 = merged[i][1]
            j = i
            while j >= 0 and merged[j][0] == merged[i][0]:
                merged[j][1] = group_col1
                j -= 1
        i -= 1

    return merged


def parse_profstandart(html_content):
    doc = lxml_html.document_fromstring(html_content)
    cont_txt = doc.find('.//div[@id="cont_txt"]')
    if cont_txt is None:
        raise ValueError("Could not find <div id='cont_txt'> in HTML")

    inner_html = lxml_html.tostring(cont_txt, method='html', encoding='unicode')
    table_rx = re.compile(r'<table[^>]*>(.*?)</table>', re.DOTALL)

    output = []

    # ── locate section boundaries ──────────────────────────────────────────

    sec1 = re.search(r'<h3>\s*I\.\s*Общие сведения\s*</h3>', inner_html)
    sec2 = re.search(r'<h3>\s*II\.\s*Описание трудовых функций', inner_html)
    sec3 = re.search(r'<h3>\s*III\.\s*Характеристика обобщенных', inner_html)
    sec4 = re.search(r'<h3>\s*IV\.\s*Сведения об организациях', inner_html)

    if not (sec1 and sec2 and sec3):
        raise ValueError("Could not find section boundaries I / II / III")

    # ── Title block ────────────────────────────────────────────────────────

    title_html = inner_html[:sec1.start()]
    output.append(format_title_block(title_html))

    # ── Section I: Общие сведения ──────────────────────────────────────────

    output.append('## I. Общие сведения')
    output.append('')

    sec1_html = inner_html[sec1.end():sec2.start()]
    sec1_tables_raw = list(table_rx.finditer(sec1_html))

    # Classify Sec I tables by content:
    # T1: main activity (Деятельность по...)
    # T2: purpose (Повышение эффективности...)
    # T3: OKZ (1213/2421)
    # T4: OKVED (70.22)
    if sec1_tables_raw:
        for tm in sec1_tables_raw:
            rows = extract_table_rows(tm.group(0))
            if not rows:
                continue
            all_text = ' '.join(' '.join(r) for r in rows).lower()

            if 'деятельность по' in all_text:
                formatted = format_sec1_activity_table(rows)
            elif 'повышение эффективности' in all_text or 'основная цель' in all_text:
                formatted = format_sec1_purpose_table(rows)
            elif re.search(r'\b1213\b', all_text) or re.search(r'\b2421\b', all_text):
                formatted = format_sec1_okz_table(rows)
            elif re.search(r'\b70\.22\b', all_text):
                formatted = format_sec1_okved_table(rows)
            else:
                formatted = classify_and_format_table(rows)

            if formatted:
                output.append(formatted)

    output.append('')

    # ── Section II: Функциональная карта ────────────────────────────────────

    output.append('## II. Функциональная карта вида профессиональной деятельности')
    output.append('')

    sec2_html = inner_html[sec2.end():sec3.start()]
    tables2 = []
    for tm in table_rx.finditer(sec2_html):
        rows = extract_table_rows(tm.group(0), min_text_len=2)
        if rows and len(rows) > 5:
            tables2.append(rows)
    if tables2:
        main = max(tables2, key=len)
        main = merge_rowspan_rows(main)

        header = main[1] if len(main) > 1 else (main[0] if main[0] else [''] * 6)
        data_rows = main[2:] if len(main) > 2 else main[1:]

        lines = ['| ' + ' | '.join(c if c else ' ' for c in header) + ' |']
        lines.append('| ' + ' | '.join('---' for _ in header) + ' |')
        for row in data_rows:
            padded = (row + [''] * 6)[:6]
            lines.append('| ' + ' | '.join(c if c else ' ' for c in padded) + ' |')
        output.append('\n'.join(lines))
    output.append('')

    # ── Section III: Характеристика ОТФ ─────────────────────────────────────

    sec3_start_pos = sec3.start()
    sec3_end_pos = sec4.start() if sec4 else len(inner_html)
    sec3_html = inner_html[sec3_start_pos:sec3_end_pos]

    output.append('## III. Характеристика обобщенных трудовых функций')
    output.append('')

    otf_rx = re.compile(r'<h4>\s*(\d+\.\d+\.\s*Обобщенная трудовая функция)\s*</h4>')
    otf_matches = list(otf_rx.finditer(sec3_html))

    tf_rx = re.compile(
        r'<div[^>]*>\s*<b>\s*(\d+\.\d+\.\d+\.\s*Трудовая функция)\s*</b>\s*(?:<br\s*/?>\s*)?</div>'
    )

    for i, m in enumerate(otf_matches):
        otf_title = m.group(1).strip()
        otf_end = otf_matches[i + 1].start() if i + 1 < len(otf_matches) else len(sec3_html)
        otf_html = sec3_html[m.start():otf_end]

        output.append(f'### {otf_title}')
        output.append('')

        tf_matches = list(tf_rx.finditer(otf_html))

        if tf_matches:
            otf_header = otf_html[:tf_matches[0].start()]
            for tm in table_rx.finditer(otf_header):
                rows = extract_table_rows(tm.group(0))
                formatted = classify_and_format_table(rows)
                if formatted:
                    output.append(formatted)
            output.append('')

            for j, tf_m in enumerate(tf_matches):
                tf_title = tf_m.group(1).strip()
                tf_start = tf_m.start()
                tf_end = tf_matches[j + 1].start() if j + 1 < len(tf_matches) else len(otf_html)
                tf_html = otf_html[tf_start:tf_end]

                output.append(f'#### {tf_title}')
                output.append('')

                for tm in table_rx.finditer(tf_html):
                    rows = extract_table_rows(tm.group(0))
                    if not rows:
                        continue
                    formatted = classify_and_format_table(rows)
                    if formatted:
                        output.append(formatted)
                        output.append('')

        output.append('')

    # ── Section IV: Сведения об организациях-разработчиках ──────────────────

    if sec4:
        sec4_html = inner_html[sec4.start():]

        # Strip PDF download link and ad scripts after tables
        pdf_idx = sec4_html.find('Скачать в PDF')
        if pdf_idx > 0:
            sec4_html = sec4_html[:pdf_idx]

        output.append('## IV. Сведения об организациях - разработчиках профессионального стандарта')
        output.append('')

        # Find subsections 4.1 and 4.2
        sub41 = re.search(r'<h4>\s*4\.1\.\s*', sec4_html)
        sub42 = re.search(r'<h4>\s*4\.2\.\s*', sec4_html)

        if sub41:
            sub41_end = sub42.start() if sub42 else len(sec4_html)
            sub41_html = sec4_html[sub41.start():sub41_end]
            output.append('### 4.1. Ответственная организация-разработчик')
            output.append('')
            for tm in table_rx.finditer(sub41_html):
                rows = extract_table_rows(tm.group(0))
                if rows:
                    formatted = format_developer_table(rows)
                    if formatted:
                        output.append(formatted)
            output.append('')

        if sub42:
            sub42_html = sec4_html[sub42.start():]
            output.append('### 4.2. Наименования организаций-разработчиков')
            output.append('')
            for tm in table_rx.finditer(sub42_html):
                rows = extract_table_rows(tm.group(0))
                if rows:
                    formatted = format_developer_table(rows)
                    if formatted:
                        output.append(formatted)
            output.append('')

    result = '\n'.join(output)
    result = re.sub(r'\n{4,}', '\n\n\n', result)

    return result.strip() + '\n'


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Parse professional standard from classinform.ru HTML to Markdown'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', help='URL of the profstandart page on classinform.ru')
    group.add_argument('--file', help='Path to local HTML file')
    parser.add_argument('--output', '-o', default='-', help='Output file (default: stdout)')
    parser.add_argument('--encoding', default='utf-8', help='Output encoding (default: utf-8)')
    args = parser.parse_args()

    if args.url:
        import urllib.request
        req = urllib.request.Request(
            args.url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible)'}
        )
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
        ct = resp.headers.get('Content-Type', '')
        enc = 'utf-8'
        if 'charset=' in ct:
            enc = ct.split('charset=')[-1].split(';')[0].strip()
        try:
            html_content = raw.decode(enc)
        except UnicodeDecodeError:
            html_content = raw.decode(enc, errors='replace')
    elif args.file:
        with open(args.file, 'rb') as f:
            raw = f.read()
        try:
            html_content = raw.decode('utf-8')
        except UnicodeDecodeError:
            try:
                html_content = raw.decode('windows-1251')
            except UnicodeDecodeError:
                html_content = raw.decode('utf-8', errors='replace')

    markdown = parse_profstandart(html_content)

    if args.output == '-':
        print(markdown)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)) or '.', exist_ok=True)
        with open(args.output, 'w', encoding=args.encoding) as f:
            f.write(markdown)
        print(f"Written to {args.output}")


if __name__ == '__main__':
    main()
