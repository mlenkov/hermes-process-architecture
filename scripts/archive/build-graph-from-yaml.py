#!/usr/bin/env python3
"""Deterministic task-centric graph builder.

Reads YAML-structured profstandart 07.007, produces Dobsongraph JSON with
task-centric topology: each ТД is a node with action_verb/action_object,
connected to profile (executor), ТФ, skills, knowledge, and sequential 'next' edges.

Usage:
    python3 scripts/build-graph-from-yaml.py ARCHITECTURE/docs/standards/07.007

Output:
    graphify-out/.graphify_semantic.json  (nodes + edges + hyperedges)
    graphify-out/.graphify_detect.json     (corpus metadata)
"""

import hashlib
import json
import re
import sys
from pathlib import Path

YAML_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('docs/standards/07.007')
OUT_DIR = Path('graphify-out')

PROFILE_MAP = {
    'А': {'title': 'Специалист по регламентации бизнес-процессов', 'level': 6},
    'В': {'title': 'Процессный аналитик', 'level': 6},
    'С': {'title': 'Процессный методолог', 'level': 7},
    'D': {'title': 'Процессный архитектор', 'level': 7},
}


def mk_id(*parts):
    raw = '_'.join(str(p) for p in parts if p)
    raw = raw.lower().strip()
    raw = re.sub(r'[^a-zа-яё0-9_]+', '_', raw, flags=re.UNICODE)
    raw = re.sub(r'_+', '_', raw)
    return raw.strip('_')


def text_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:12]


def drop_nulls(obj):
    if isinstance(obj, dict):
        return {k: drop_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [drop_nulls(i) for i in obj]
    return obj


def node(label, **kw):
    n = {'file_type': 'concept'}
    n['label'] = label
    n.update({k: v for k, v in kw.items() if v is not None})
    return n


def edge(source, target, relation, **kw):
    e = {'confidence': 'EXTRACTED', 'confidence_score': 1.0, 'weight': 1.0}
    e['source'] = source
    e['target'] = target
    e['relation'] = relation
    e.update({k: v for k, v in kw.items() if v is not None})
    return e


def parse_task_text(text):
    parts = text.strip().split(maxsplit=1)
    verb = parts[0]
    obj = parts[1] if len(parts) > 1 else ''
    return verb, obj


def section_file(code, yaml_files):
    if not code:
        return 'otf-section-unknown.yaml'
    code_upper = code.upper().strip()
    cyr_map = {'А': '1', 'В': '2', 'С': '3'}
    lat_map = {'A': '1', 'B': '2', 'C': '3', 'D': '4'}
    num = cyr_map.get(code_upper) or lat_map.get(code_upper) or code_upper.lower()
    candidate = f'otf-section-{num}.yaml'
    if any(f.name == candidate for f in yaml_files):
        return candidate
    matches = sorted(f.name for f in yaml_files if f.name.startswith('otf-section-'))
    if matches:
        return matches[0]
    return 'otf-section-unknown.yaml'


def read_yaml_dir(yaml_dir):
    import yaml
    meta = {}
    otfs = []
    yaml_files = list(yaml_dir.glob('*.yaml'))
    for f in yaml_files:
        with open(f) as fh:
            data = yaml.safe_load(fh)
        if data is None:
            continue
        if data.get('type') == 'professional_standard':
            data['_source_file'] = f.name
            meta = data
        elif data.get('type') == 'generalized_labor_function':
            data['_source_file'] = f.name
            otfs.append(data)
    return meta, otfs, yaml_files


def collect_skills_knowledge(otfs):
    unique = {}
    for otf in otfs:
        for tf in otf.get('labor_functions', []):
            for text in tf.get('необходимые_умения', []):
                unique[('skill', text)] = True
            for text in tf.get('необходимые_знания', []):
                unique[('knowledge', text)] = True
    return list(unique.keys())


def build_graph():
    import yaml
    meta, otfs, yaml_files = read_yaml_dir(YAML_DIR)
    standard_id = mk_id('standards', meta.get('code', 'unknown'))
    meta_file = str(YAML_DIR / 'meta.yaml')
    nodes = []
    edges = []

    code = meta.get('code', '')
    title = meta.get('title', '')

    # --- Standard node ---
    nodes.append(node(
        id=standard_id,
        label=f"Профессиональный стандарт {code}: {title}",
        file_type='standard',
        source_file=meta_file,
        source_location='meta.yaml',
    ))

    # --- Pass 1: unique skills/knowledge nodes ---
    unique_items = collect_skills_knowledge(otfs)
    text_to_node_id = {}
    for cat, text in unique_items:
        h = text_hash(text)
        nid = mk_id(standard_id, cat, h)
        text_to_node_id[(cat, text)] = nid
        if not any(n.get('id') == nid for n in nodes):
            nodes.append(node(
                id=nid,
                label=text,
                file_type=cat,
                source_file=meta_file,
                source_location='meta.yaml',
            ))

    # --- Profile nodes ---
    profile_to_id = {}
    for otf_code, pdata in PROFILE_MAP.items():
        pid = mk_id(standard_id, 'profile', pdata['title'])
        profile_to_id[otf_code] = pid
        if not any(n.get('id') == pid for n in nodes):
            nodes.append(node(
                id=pid,
                label=pdata['title'],
                file_type='profile',
                level=pdata['level'],
                source_file=meta_file,
                source_location='meta.yaml',
            ))

    # --- IDEF0 data-node registry ---
    # Collect TF-level inputs/outputs from execution blocks so we can
    # reuse them across TFs (e.g. D/01.7 output → D/02.7 input).
    idef0_output_registry = {}   # output_id → (source_code, node_id)
    def ensure_idef0_node(data_id, label, file_type, source_file, source_location):
        """Create a data node once; return its ID."""
        nid = mk_id(standard_id, file_type, data_id)
        if not any(n.get('id') == nid for n in nodes):
            nodes.append(node(
                id=nid,
                label=label or data_id,
                file_type=file_type,
                source_file=source_file,
                source_location=source_location,
            ))
        return nid

    # --- Pass 2: ОТФ, ТФ, ТД, edges ---
    for otf in otfs:
        otf_code = otf.get('code', '')
        otf_name = otf.get('name', '')
        otf_id = mk_id(standard_id, 'otf', otf_code)
        otf_rel = section_file(otf_code, yaml_files)
        otf_file = str(YAML_DIR / otf_rel)

        profile_id = profile_to_id.get(otf_code)

        nodes.append(node(
            id=otf_id,
            label=f"ОТФ-{otf_code}: {otf_name}",
            file_type='generalized_labor_function',
            source_file=otf_file,
            source_location=otf_rel,
        ))
        edges.append(edge(otf_id, standard_id, 'part_of',
                          source_file=otf_file, source_location=otf_rel))

        for tf in otf.get('labor_functions', []):
            tf_code = tf.get('code', '')
            tf_name = tf.get('name', '')
            tf_id = mk_id(standard_id, 'tf', re.sub(r'[^\w]', '_', tf_code))

            nodes.append(node(
                id=tf_id,
                label=f"ТФ {tf_code}: {tf_name}",
                file_type='labor_function',
                source_file=otf_file,
                source_location=otf_rel,
            ))
            edges.append(edge(tf_id, otf_id, 'part_of',
                              source_file=otf_file, source_location=otf_rel))

            # Process ТД
            task_ids = []
            tasks = tf.get('трудовые_действия', [])
            for idx, text in enumerate(tasks, 1):
                verb, obj = parse_task_text(text)
                task_id = mk_id(standard_id, 'task', re.sub(r'[^\w]', '_', tf_code), str(idx))
                task_ids.append(task_id)

                nodes.append(node(
                    id=task_id,
                    label=text,
                    file_type='task',
                    action_verb=verb,
                    action_object=obj,
                    sequence_index=idx,
                    source_file=otf_file,
                    source_location=otf_rel,
                ))
                edges.append(edge(task_id, tf_id, 'part_of',
                                  source_file=otf_file, source_location=otf_rel))
                if profile_id:
                    edges.append(edge(task_id, profile_id, 'executed_by',
                                      source_file=otf_file, source_location=otf_rel))

                for skill_text in tf.get('необходимые_умения', []):
                    sid = text_to_node_id.get(('skill', skill_text))
                    if sid:
                        edges.append(edge(task_id, sid, 'requires_skill',
                                          source_file=otf_file, source_location=otf_rel))

                for know_text in tf.get('необходимые_знания', []):
                    kid = text_to_node_id.get(('knowledge', know_text))
                    if kid:
                        edges.append(edge(task_id, kid, 'requires_knowledge',
                                          source_file=otf_file, source_location=otf_rel))

            for i in range(len(task_ids) - 1):
                edges.append(edge(task_ids[i], task_ids[i + 1], 'next',
                                  source_file=otf_file, source_location=otf_rel))

            # --- IDEF0 ICOM: inputs / outputs from execution block ---
            exec_block = tf.get('execution', {})
            if exec_block:
                # TF-level ICOM
                for inp in exec_block.get('inputs', []):
                    iid = inp['id']
                    src_tf = inp.get('source_tf')
                    # Reuse output from source TF if available
                    if src_tf and iid in idef0_output_registry:
                        existing_nid = idef0_output_registry[iid][1]
                        edges.append(edge(existing_nid, tf_id, 'input_to',
                                          source_file=otf_file, source_location=otf_rel))
                    else:
                        label = inp.get('description', iid)
                        nid = ensure_idef0_node(iid, label, 'idef0_input', otf_file, otf_rel)
                        edges.append(edge(nid, tf_id, 'input_to',
                                          source_file=otf_file, source_location=otf_rel))

                for out in exec_block.get('outputs', []):
                    oid = out['id']
                    label = out.get('description', oid)
                    nid = ensure_idef0_node(oid, label, 'idef0_output', otf_file, otf_rel)
                    edges.append(edge(tf_id, nid, 'output_from',
                                      source_file=otf_file, source_location=otf_rel))
                    idef0_output_registry[oid] = (tf.get('code', ''), nid)

                # Per-action ICOM
                exec_actions = exec_block.get('actions', [])
                for ea in exec_actions:
                    idx = ea.get('index')
                    if idx is None or idx >= len(task_ids):
                        continue
                    act_nid = task_ids[idx]

                    for inp_id in ea.get('inputs', []):
                        # Reuse or create input node
                        if inp_id in idef0_output_registry:
                            nid = idef0_output_registry[inp_id][1]
                        else:
                            nid = ensure_idef0_node(inp_id, inp_id, 'idef0_input', otf_file, otf_rel)
                        edges.append(edge(nid, act_nid, 'input_to',
                                          source_file=otf_file, source_location=otf_rel))

                    for out_id in ea.get('outputs', []):
                        nid = ensure_idef0_node(out_id, out_id, 'idef0_output', otf_file, otf_rel)
                        edges.append(edge(act_nid, nid, 'output_from',
                                          source_file=otf_file, source_location=otf_rel))
                        # Register intermediate outputs so downstream actions can reuse
                        idef0_output_registry[out_id] = (tf.get('code', ''), nid)

    # --- Hyperedges ---
    hyperedge_groups = []

    def he_id(name):
        return mk_id(standard_id, 'he', name)

    comm_nodes = [n for n in nodes
                  if n.get('file_type') == 'skill'
                  and ('коммуникаци' in n['label'].lower()
                       or 'консенсус' in n['label'].lower())]
    if len(comm_nodes) >= 1:
        hyperedge_groups.append({
            'id': he_id('skills_communication'),
            'label': 'Навыки коммуникации и согласования',
            'nodes': [n['id'] for n in comm_nodes],
            'relation': 'participate_in',
            'confidence': 'INFERRED',
            'confidence_score': 0.95,
        })

    foundation_kw = ['теория процессного', 'системного подхода', 'операционного менеджмента']
    found_nodes = [n for n in nodes
                   if n.get('file_type') == 'knowledge'
                   and any(kw in n['label'].lower() for kw in foundation_kw)]
    if len(found_nodes) >= 2:
        hyperedge_groups.append({
            'id': he_id('knowledge_foundations'),
            'label': 'Фундаментальные знания процессного управления',
            'nodes': [n['id'] for n in found_nodes],
            'relation': 'participate_in',
            'confidence': 'INFERRED',
            'confidence_score': 0.95,
        })

    sw_nodes = [n for n in nodes
                if n.get('file_type') in ('skill', 'knowledge')
                and 'программн' in n['label'].lower()]
    if len(sw_nodes) >= 3:
        hyperedge_groups.append({
            'id': he_id('software_tools'),
            'label': 'Программное обеспечение и инструменты',
            'nodes': [n['id'] for n in sw_nodes],
            'relation': 'participate_in',
            'confidence': 'INFERRED',
            'confidence_score': 0.95,
        })

    anal_nodes = [n for n in nodes
                  if n.get('file_type') == 'skill'
                  and ('анализировать' in n['label'].lower()
                       or 'систематизировать' in n['label'].lower())]
    if len(anal_nodes) >= 3:
        hyperedge_groups.append({
            'id': he_id('skills_analytical'),
            'label': 'Навыки анализа и систематизации',
            'nodes': [n['id'] for n in anal_nodes],
            'relation': 'participate_in',
            'confidence': 'INFERRED',
            'confidence_score': 0.95,
        })

    model_nodes = [n for n in nodes
                   if n.get('file_type') == 'knowledge'
                   and ('моделирован' in n['label'].lower()
                        or 'нотации' in n['label'].lower()
                        or 'декомпозици' in n['label'].lower())]
    if len(model_nodes) >= 3:
        hyperedge_groups.append({
            'id': he_id('knowledge_modeling'),
            'label': 'Методология моделирования и декомпозиции',
            'nodes': [n['id'] for n in model_nodes],
            'relation': 'participate_in',
            'confidence': 'INFERRED',
            'confidence_score': 0.95,
        })

    for hg in hyperedge_groups:
        edges.append({
            'source': hg['id'],
            'target': hg['id'],
            'relation': 'hyperedge',
            'hyperedges': [hg],
            'confidence': hg['confidence'],
            'confidence_score': hg['confidence_score'],
            'weight': 1.0,
        })

    return nodes, edges


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print('Building task-centric graph from YAML...')
    nodes, edges = build_graph()
    print(f'  {len(nodes)} nodes, {len(edges)} edges')

    nodes = [drop_nulls(n) for n in nodes]
    hyperedges = []
    clean_edges = []
    for e in edges:
        if 'hyperedges' in e:
            hyperedges.extend(e.pop('hyperedges'))
        clean_edges.append(e)

    sem_path = OUT_DIR / '.graphify_semantic.json'
    with open(sem_path, 'w', encoding='utf-8') as f:
        json.dump({
            'nodes': nodes,
            'edges': clean_edges,
            'hyperedges': hyperedges,
            'input_tokens': 0,
            'output_tokens': 0,
        }, f, indent=2, ensure_ascii=False)
    print(f'  Written {sem_path}')

    detect_path = OUT_DIR / '.graphify_detect.json'
    with open(detect_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_files': 5,
            'total_words': 0,
            'files': {
                'document': [str(p) for p in sorted(YAML_DIR.glob('*.yaml'))],
                'code': [],
                'paper': [],
                'image': [],
                'video': [],
            },
            'scan_root': str(YAML_DIR.resolve()),
        }, f, indent=2, ensure_ascii=False)
    print(f'  Written {detect_path}')

    print(f'\nGraph stats:')
    ft_counts = {}
    for n in nodes:
        ft = n.get('file_type', '?')
        ft_counts[ft] = ft_counts.get(ft, 0) + 1
    for ft, cnt in sorted(ft_counts.items()):
        print(f'  {ft}: {cnt}')
    print(f'  hyperedges: {len(hyperedges)}')

    rel_counts = {}
    for e in clean_edges:
        rel = e.get('relation', '?')
        rel_counts[rel] = rel_counts.get(rel, 0) + 1
    for rel, cnt in sorted(rel_counts.items()):
        if rel != 'hyperedge':
            print(f'  {rel}: {cnt}')


if __name__ == '__main__':
    main()
