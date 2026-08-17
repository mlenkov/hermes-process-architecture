#!/usr/bin/env python3
"""Детерминированная приёмка кросс-стандартного делегирования (ADR-012, 8с).

Этап 3: 06.043 (делегатор) принимает контент от 06.013 (исполнителя).
Сверяет ТЗ (Этап 1) и контент-артефакт (Этап 2):
  1. request_id совпадает;
  2. перечень материалов ТЗ покрыт контентом;
  3. контент schema_valid (status generated);
  4. анти-галлюцинация: сущности контента из ТЗ/входов.

Пишет:
  - outputs/06.043/block-E/E-03.5-acceptance.yaml (verdict, evidence)
  - outputs/06.043/block-E/E-03.5-acceptance-approval-request.yaml (ADR-006)

При mismatch → verdict REJECTED, выходит с кодом 2, registry НЕ пишется.

Usage:
    python3 scripts/accept-delegation.py --standard 06.043 --tf E/03.5 \
        --tz outputs/06.043/block-E/E-03.5-content-tz.yaml \
        --content outputs/06.013/block-B/B-02.5-content-materials.yaml \
        --operator "Максим"
"""

import argparse
import datetime
import json
import sys
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--standard", required=True)
    ap.add_argument("--tf", required=True)
    ap.add_argument("--tz", required=True, help="путь к ТЗ (этап 1)")
    ap.add_argument("--content", required=True, help="путь к контент-артефакту (этап 2)")
    ap.add_argument("--operator", default="User_Operator", help="кто утверждает (HITL)")
    ap.add_argument("--request-id", required=True, help="ожидаемый request_id (напр. APR-01)")
    ap.add_argument("--registry-0613", required=False, help="путь к registry 06.013 (для evidence)")
    args = ap.parse_args()

    tz_path = Path(args.tz)
    content_path = Path(args.content)
    evidence = []

    # ── 1. Читаем и нормализуем ────────────────────────────────────
    tz = load(tz_path)
    if isinstance(tz.get("tz"), dict):
        tz = tz["tz"]
    content = load(content_path)
    if isinstance(content.get("artifact"), dict):
        content = content["artifact"]

    # ── 2. request_id ──────────────────────────────────────────────
    tz_req = tz.get("request_id")
    cont_req = content.get("request_id")
    evidence.append(f"request_id: ТЗ={tz_req}, контент={cont_req}")
    if tz_req != cont_req or tz_req != args.request_id:
        print("REJECTED: request_id mismatch")
        sys.exit(2)

    # ── 3. Перечень материалов ─────────────────────────────────────
    tz_full = load(tz_path)
    tz_materials = {m["material_id"] for m in tz_full.get("materials", [])}
    cont_full = load(content_path)
    cont_materials = {k for k in cont_full.keys() if k.startswith("M-")}
    missing = sorted(tz_materials - cont_materials)
    evidence.append(f"материалы: ТЗ={sorted(tz_materials)}, контент={sorted(cont_materials)}, не покрыто={missing or 'нет'}")
    if missing:
        print(f"REJECTED: контент не покрывает материалы ТЗ: {missing}")
        sys.exit(2)

    # ── 4. schema_valid (status generated) ─────────────────────────
    cont_status = content.get("status")
    evidence.append(f"контент status: {cont_status}")
    if cont_status != "generated":
        print(f"REJECTED: контент status='{cont_status}' != 'generated'")
        sys.exit(2)

    # ── 5. Анти-галлюцинация: USP/факты контента из ТЗ ────────────
    # (проба: USP контента ⊆ USP ТЗ)
    tz_usp = {str(u).lower() for u in (tz.get("product_usp") or [])}
    cont_usp = {str(u).lower() for u in content.get("product_usp") or []}
    invented_usp = [u for u in cont_usp if u and not any(u in t or t in u for t in tz_usp)]
    evidence.append(f"USP контента вне ТЗ: {invented_usp or 'нет'}")
    if invented_usp:
        print(f"REJECTED: выдуманные USP в контенте: {invented_usp}")
        sys.exit(2)

    # ── SUCCESS ────────────────────────────────────────────────────
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    apr_id = f"APR-{args.request_id.split('-')[-1]:s}" if "-" in args.request_id else args.request_id
    request_id = args.request_id

    accept_dir = ROOT / "outputs" / args.standard / "block-E"
    accept_dir.mkdir(parents=True, exist_ok=True)
    acc_path = accept_dir / f"{args.tf.replace('/', '-')}-acceptance.yaml"
    appr_path = accept_dir / f"{args.tf.replace('/', '-')}-acceptance-approval-request.yaml"

    acceptance = {
        "verdict": "PASS",
        "delegation": {"from": args.standard, "to": "06.013", "standard_0613": "06.013"},
        "request_id": request_id,
        "evidence": evidence,
        "references": {
            "tz": str(tz_path),
            "content": str(content_path),
        },
        "awaiting_approval": True,
        "timestamp": ts,
    }
    with open(acc_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(acceptance, fh, allow_unicode=True, sort_keys=False)

    approval_request = {
        "request_id": f"APPROVAL-{request_id}",
        "type": "approval_request",
        "tf_code": args.tf,
        "standard": args.standard,
        "question": (f"Утвердить приёмку делегированного контента {args.tf} "
                     f"(request {request_id}) от 06.013 copywriter?"),
        "options": [
            {"option_id": "approve", "label": "Утвердить", "description": "Контент принят, registry 06.043 фиксирует исполнение ТЗ+приёмку"},
            {"option_id": "rework", "label": "Вернуть на доработку", "description": "Контент не соответствует ТЗ, отправить копирайтеру на правки"},
        ],
        "context_ref": {"tz": str(tz_path), "content": str(content_path),
                        "acceptance": str(acc_path)},
        "awaiting_approval": True,
        "deadline": None,
        "timestamp": ts,
    }
    with open(appr_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(approval_request, fh, allow_unicode=True, sort_keys=False)

    print("ACCEPTED (PASS), awaiting HITL approval")
    print(f"  acceptance: {acc_path}")
    print(f"  approval-request: {appr_path}")
    for e in evidence:
        print(f"  • {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
