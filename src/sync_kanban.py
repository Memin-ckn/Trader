#!/usr/bin/env python3
"""
src/sync_kanban.py
Kanban Görev Senkronizasyon Motoru (Local docs/Kanban.md <---> GitHub Projects #10)

Bu modül, docs/Kanban.md dosyasındaki görevler ile GitHub üzerindeki 'Trader' (Project #10)
panosunu çift yönlü senkronize eder.

Kullanım:
    python src/sync_kanban.py --push            # Yerel Kanban.md içeriğini GitHub'a aktarır/günceller (Varsayılan)
    python src/sync_kanban.py --pull            # GitHub'daki son durumu docs/Kanban.md'ye indirir (Çakışma korumalı)
    python src/sync_kanban.py --check           # Yerel ve bulut arasındaki farkları raporlar (Salt okunur)
    python src/sync_kanban.py --move "UI" --to "In progress" # Görevi yerelde ve GitHub'da taşır
    python src/sync_kanban.py --install-hook    # Git pre-commit kancasını (.git/hooks/pre-commit) kurar
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Dinamik kök dizin ekleme
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from src.paths import BASE_DIR, KANBAN_FILE
except ImportError:
    BASE_DIR = _PROJECT_ROOT
    KANBAN_FILE = BASE_DIR / "docs" / "Kanban.md"

# GitHub Proje Sabitleri
PROJECT_ID = "PVT_kwHOBY31cs4Bqm_E"
PROJECT_NUM = "10"
PROJECT_OWNER = "Memin-ckn"
STATUS_FIELD_ID = "PVTSSF_lAHOBY31cs4Bqm_Ezho9XnY"

STATUS_OPTIONS = {
    "Backlog": "f75ad846",
    "In progress": "47fc9ee4",
    "In review": "df73e18b",
    "Done": "98236657",
}

SECTION_MAP = {
    "to do": "Backlog",
    "todo": "Backlog",
    "backlog": "Backlog",
    "in progress": "In progress",
    "inprogress": "In progress",
    "testing": "In review",
    "in review": "In review",
    "inreview": "In review",
    "complete": "Done",
    "done": "Done",
}

STATUS_TO_SECTION_TITLE = {
    "Backlog": "To do",
    "In progress": "In Progress",
    "In review": "Testing",
    "Done": "Complete",
}


def _normalize_title(title: str) -> str:
    """Başlığı karşılaştırma amacıyla küçük harfe, kod işaretleri ve boşluklardan arındırılmış hale getirir."""
    t = title.replace("`", "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def parse_kanban_markdown(content: str) -> dict[str, list[dict[str, str]]]:
    """docs/Kanban.md içeriğini parse ederek statü bazlı görev sözlüğü döner."""
    sections: dict[str, list[dict[str, str]]] = {
        "Backlog": [],
        "In progress": [],
        "In review": [],
        "Done": [],
    }

    current_status: str | None = None
    current_item: dict[str, str] | None = None

    lines = content.splitlines()
    for line in lines:
        stripped = line.strip()

        # Bölüm başlığı tespiti (# To do, # In Progress, vb.)
        if line.startswith("#"):
            if current_item and current_status:
                current_item["body"] = current_item["body"].strip()
                sections[current_status].append(current_item)
                current_item = None

            header_text = line.lstrip("#").strip().lower()
            current_status = SECTION_MAP.get(header_text)
            continue

        if not current_status:
            continue

        # Ana görev maddesi tespiti (- Görev Adı)
        if line.startswith("- ") or line.startswith("* "):
            if current_item:
                current_item["body"] = current_item["body"].strip()
                sections[current_status].append(current_item)

            raw_title = line[2:].strip()
            current_item = {
                "title": raw_title,
                "body": "",
                "status": current_status,
            }
        elif current_item is not None:
            # Görev gövdesi / alt maddeleri
            if current_item["body"]:
                current_item["body"] += "\n" + line
            else:
                current_item["body"] = line

    if current_item and current_status:
        current_item["body"] = current_item["body"].strip()
        sections[current_status].append(current_item)

    return sections


def render_kanban_markdown(sections: dict[str, list[dict[str, str]]]) -> str:
    """Statü bazlı görev sözlüğünden standart Kanban.md içeriği üretir."""
    lines: list[str] = [
        "> 🔗 **Canlı GitHub Project Panosu:** [Trader Project #10](https://github.com/users/Memin-ckn/projects/10)",
        "",
    ]

    order = ["Backlog", "In progress", "In review", "Done"]
    for status in order:
        header_title = STATUS_TO_SECTION_TITLE[status]
        lines.append(f"# {header_title}")
        items = sections.get(status, [])
        for item in items:
            title = item["title"]
            body = item.get("body", "").strip()
            lines.append(f"- {title}")
            if body:
                for b_line in body.splitlines():
                    lines.append(b_line if b_line.startswith(" ") or b_line.startswith("\t") else f"    {b_line}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _run_gh_command(args: list[str]) -> str:
    """gh CLI komutunu çalıştırır ve çıktısını döner."""
    cmd = ["gh"] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"GitHub CLI komutu başarısız oldu: {' '.join(cmd)}\n"
            f"Stderr: {res.stderr}\nStdout: {res.stdout}"
        )
    return res.stdout


def fetch_github_items(owner: str = PROJECT_OWNER, project_num: str = PROJECT_NUM) -> list[dict[str, Any]]:
    """GitHub Project #10 üzerindeki tüm kartları çeker."""
    stdout = _run_gh_command(
        ["project", "item-list", project_num, "--owner", owner, "--format", "json"]
    )
    data = json.loads(stdout)
    items = data.get("items", [])
    result: list[dict[str, Any]] = []
    for it in items:
        content = it.get("content", {})
        title = it.get("title") or content.get("title", "")
        body = content.get("body", "")
        item_id = it.get("id", "")
        status = it.get("status", "")
        result.append({
            "id": item_id,
            "title": title,
            "body": body,
            "status": status,
        })
    return result


def check_sync_status(kanban_path: Path = KANBAN_FILE) -> dict[str, Any]:
    """Yerel Kanban.md ile GitHub Project durumunu karşılaştırır."""
    if not kanban_path.exists():
        raise FileNotFoundError(f"Kanban dosyası bulunamadı: {kanban_path}")

    content = kanban_path.read_text(encoding="utf-8")
    local_sections = parse_kanban_markdown(content)

    local_items: list[dict[str, str]] = []
    for st, items in local_sections.items():
        for item in items:
            local_items.append(item)

    gh_items = fetch_github_items()

    gh_by_norm_title: dict[str, dict[str, Any]] = {}
    for g in gh_items:
        norm = _normalize_title(g["title"])
        gh_by_norm_title[norm] = g

    status_diffs: list[dict[str, Any]] = []
    missing_on_github: list[dict[str, str]] = []

    matched_gh_ids: set[str] = set()

    for l in local_items:
        norm = _normalize_title(l["title"])
        if norm in gh_by_norm_title:
            gh_item = gh_by_norm_title[norm]
            matched_gh_ids.add(gh_item["id"])
            if gh_item["status"] != l["status"]:
                status_diffs.append({
                    "title": l["title"],
                    "local_status": l["status"],
                    "github_status": gh_item["status"],
                    "github_id": gh_item["id"],
                })
        else:
            missing_on_github.append(l)

    missing_locally = [g for g in gh_items if g["id"] not in matched_gh_ids]

    in_sync = (len(status_diffs) == 0 and len(missing_on_github) == 0 and len(missing_locally) == 0)

    return {
        "in_sync": in_sync,
        "status_diffs": status_diffs,
        "missing_on_github": missing_on_github,
        "missing_locally": missing_locally,
        "total_local": len(local_items),
        "total_github": len(gh_items),
    }


def push_to_github(kanban_path: Path = KANBAN_FILE, dry_run: bool = False) -> None:
    """Yerel Kanban.md içeriğindeki değişiklikleri GitHub Project panosuna yansıtır."""
    print(f"[*] Yerel Kanban inceleniyor: {kanban_path}")
    diff = check_sync_status(kanban_path)

    if diff["in_sync"]:
        print("✓ Yerel dosya ve GitHub Project panosu zaten %100 senkronize.")
        return

    # Statüsü değişenleri güncelle
    for s in diff["status_diffs"]:
        title = s["title"]
        target_status = s["local_status"]
        option_id = STATUS_OPTIONS.get(target_status)
        item_id = s["github_id"]

        print(f"-> Güncelleniyor: '{title}' ({s['github_status']} -> {target_status})...")
        if not dry_run and option_id:
            _run_gh_command([
                "project", "item-edit",
                "--id", item_id,
                "--project-id", PROJECT_ID,
                "--field-id", STATUS_FIELD_ID,
                "--single-select-option-id", option_id,
            ])

    # GitHub'da eksik olan yeni görevleri oluştur
    for m in diff["missing_on_github"]:
        title = m["title"]
        body = m["body"]
        status = m["status"]
        option_id = STATUS_OPTIONS.get(status)

        print(f"+ Yeni Kart Ekleniyor: '{title}' [{status}]...")
        if not dry_run:
            create_out = _run_gh_command([
                "project", "item-create", PROJECT_NUM,
                "--owner", PROJECT_OWNER,
                "--title", title,
                "--body", body,
                "--format", "json",
            ])
            data = json.loads(create_out)
            item_id = data["id"]
            if option_id:
                _run_gh_command([
                    "project", "item-edit",
                    "--id", item_id,
                    "--project-id", PROJECT_ID,
                    "--field-id", STATUS_FIELD_ID,
                    "--single-select-option-id", option_id,
                ])

    print("✓ GitHub Project senkronizasyonu tamamlandı!")


def pull_from_github(kanban_path: Path = KANBAN_FILE, force: bool = False, dry_run: bool = False) -> None:
    """GitHub Project panosundaki kartları çekerek yerel docs/Kanban.md dosyasını günceller."""
    # Çakışma kontrolü (Git working tree dirty check)
    git_status = subprocess.run(
        ["git", "status", "--porcelain", str(kanban_path)],
        capture_output=True,
        text=True,
        cwd=BASE_DIR,
    )
    if git_status.stdout.strip() and not force:
        print(
            "UYARI: docs/Kanban.md üzerinde kaydedilmemiş/commit edilmemiş yerel değişiklikler var!",
            file=sys.stderr,
        )
        print(
            "Çakışmayı önlemek için önce yerel değişikliklerinizi commit'leyin veya '--force' kullanın.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[*] GitHub Project #{PROJECT_NUM} kartları çekiliyor...")
    gh_items = fetch_github_items()

    sections: dict[str, list[dict[str, str]]] = {
        "Backlog": [],
        "In progress": [],
        "In review": [],
        "Done": [],
    }

    for it in gh_items:
        st = it.get("status") or "Backlog"
        if st not in sections:
            st = "Backlog"
        sections[st].append({
            "title": it["title"],
            "body": it.get("body", ""),
            "status": st,
        })

    rendered = render_kanban_markdown(sections)
    if dry_run:
        print("--- [DRY-RUN RENDERED KANBAN.MD] ---")
        print(rendered)
        return

    kanban_path.write_text(rendered, encoding="utf-8")
    print(f"✓ {kanban_path} dosyası GitHub Project panosundan başarıyla güncellendi ({len(gh_items)} kart).")


def move_task(title: str, target_status_raw: str, kanban_path: Path = KANBAN_FILE) -> None:
    """Belirli bir görevi hem yerel Kanban.md dosyasında hem de GitHub'da taşır."""
    norm_target = target_status_raw.strip().lower()
    target_status = SECTION_MAP.get(norm_target)
    if not target_status:
        raise ValueError(f"Geçersiz hedef statü: '{target_status_raw}'. Seçenekler: {list(STATUS_OPTIONS.keys())}")

    content = kanban_path.read_text(encoding="utf-8")
    sections = parse_kanban_markdown(content)

    found_item: dict[str, str] | None = None
    target_norm = _normalize_title(title)

    for st, items in sections.items():
        for i, item in enumerate(items):
            if _normalize_title(item["title"]) == target_norm:
                found_item = items.pop(i)
                break
        if found_item:
            break

    if not found_item:
        raise ValueError(f"Görev bulunamadı: '{title}'")

    found_item["status"] = target_status
    sections[target_status].append(found_item)

    # Yerel dosyaya yaz
    rendered = render_kanban_markdown(sections)
    kanban_path.write_text(rendered, encoding="utf-8")
    print(f"✓ Yerel Kanban: '{found_item['title']}' -> '{target_status}' taşındı.")

    # GitHub'a push et
    push_to_github(kanban_path)


def install_git_hook(base_dir: Path = BASE_DIR) -> None:
    """Git pre-commit kancasını kurar."""
    hooks_dir = base_dir / ".git" / "hooks"
    if not hooks_dir.exists():
        print(f"HATA: .git/hooks dizini bulunamadı: {hooks_dir}", file=sys.stderr)
        sys.exit(1)

    pre_commit_file = hooks_dir / "pre-commit"
    hook_script = f"""#!/bin/bash
# Pre-commit hook: docs/Kanban.md değişmişse GitHub Project #10 ile otomatik senkronize et
if git diff --cached --name-only | grep -q "docs/Kanban.md"; then
    echo ">> [Git Hook] docs/Kanban.md değişikliği tespit edildi. GitHub Project #10 senkronize ediliyor..."
    python3 "{_PROJECT_ROOT / 'src' / 'sync_kanban.py'}" --push
    if [ $? -ne 0 ]; then
        echo ">> [HATA] GitHub Project senkronizasyonu başarısız oldu! Commit engellendi."
        exit 1
    fi
fi
exit 0
"""
    pre_commit_file.write_text(hook_script, encoding="utf-8")
    os.chmod(pre_commit_file, 0o755)
    print(f"✓ Git pre-commit hook başarıyla kuruldu: {pre_commit_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kanban Görev Senkronizasyon Motoru")
    parser.add_argument("--push", action="store_true", help="docs/Kanban.md içeriğini GitHub'a yükler (Varsayılan)")
    parser.add_argument("--pull", action="store_true", help="GitHub Project panosunu yerel docs/Kanban.md'ye indirir")
    parser.add_argument("--check", action="store_true", help="Senkronizasyon durumunu kontrol eder (Değişiklik yapmaz)")
    parser.add_argument("--force", action="store_true", help="Pull sırasında yerel değişiklik uyarısını ezer")
    parser.add_argument("--dry-run", action="store_true", help="Değişiklik yapmadan simüle eder")
    parser.add_argument("--install-hook", action="store_true", help="Git pre-commit kancasını (.git/hooks/pre-commit) kurar")
    parser.add_argument("--move", type=str, help="Taşınacak görev başlığı")
    parser.add_argument("--to", type=str, help="Hedef statü (Backlog, In progress, In review, Done)")

    args = parser.parse_args()

    if args.install_hook:
        install_git_hook()
        return

    if args.move:
        if not args.to:
            print("HATA: --move ile birlikte --to <statü> belirtilmelidir.", file=sys.stderr)
            sys.exit(1)
        move_task(args.move, args.to)
        return

    if args.check:
        print("[*] Kanban senkronizasyon durumu kontrol ediliyor...")
        diff = check_sync_status()
        if diff["in_sync"]:
            print(f"✓ Sistem tam senkron! Toplam {diff['total_local']} kart her iki tarafta da güncel.")
            sys.exit(0)
        else:
            print(f"UYARI: Senkronizasyon farkı tespit edildi!")
            if diff["status_diffs"]:
                print("  Statü Farklılıkları:")
                for s in diff["status_diffs"]:
                    print(f"    - {s['title']}: Yerel [{s['local_status']}] != GitHub [{s['github_status']}]")
            if diff["missing_on_github"]:
                print("  GitHub'da Olmayan Yerel Maddeler:")
                for m in diff["missing_on_github"]:
                    print(f"    - {m['title']} [{m['status']}]")
            if diff["missing_locally"]:
                print("  Yerelde Olmayan GitHub Maddeleri:")
                for g in diff["missing_locally"]:
                    print(f"    - {g['title']} [{g['status']}]")
            sys.exit(1)

    if args.pull:
        pull_from_github(force=args.force, dry_run=args.dry_run)
        return

    # Varsayılan eylem: push
    push_to_github(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
