#!/usr/bin/env python3
"""One-shot migration: .scratch/spt-tank local tracker -> GitHub issues.

Map file  -> issue labelled wayfinder:map (#1 expected)
Tickets   -> issues, attached as sub-issues of the map, in ticket order
Answer    -> comment "Ответ"
research/ -> comment "Материалы исследования" on the ticket's issue
Comments  -> comment "Комментарии"
Blocked by -> native issue dependencies (probe first; fallback = body line)
Resolved   -> issue closed (state_reason=completed)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = "tarouttoo/spt-for-pkn2m"
ROOT = Path(".scratch/spt-tank")
TYPE_LABEL = {
    "research": "wayfinder:research",
    "prototype": "wayfinder:prototype",
    "grilling": "wayfinder:grilling",
    "task": "wayfinder:task",
}


def gh(endpoint, payload=None, method=None):
    cmd = ["gh", "api"]
    if method:
        cmd += ["--method", method]
    cmd.append(endpoint)
    stdin = None
    if payload is not None:
        cmd += ["--input", "-"]
        stdin = json.dumps(payload, ensure_ascii=False)
    p = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"gh api {endpoint}: {p.stderr.strip()}")
    out = p.stdout.strip()
    return json.loads(out) if out else None


def try_gh(endpoint, payload=None, method=None):
    try:
        return gh(endpoint, payload, method), True
    except RuntimeError as e:
        print(f"  ! {e}")
        return None, False


def parse_ticket(path: Path):
    text = path.read_text(encoding="utf-8")
    title_m = re.search(r"^# (.+)$", text, re.M)
    title = title_m.group(1).strip()
    ftype = re.search(r"^Type:\s*(\S+)", text, re.M).group(1)
    status = re.search(r"^Status:\s*(\S+)", text, re.M).group(1)
    blocked = re.search(r"^Blocked by:\s*(.+)$", text, re.M).group(1).strip()
    blocked = [] if blocked in ("—", "-") else [int(x) for x in re.findall(r"\d+", blocked)]

    # Body: from end of front matter to "## Answer" / "## Comments".
    fm_end = text.index("\n## ")
    body = text[fm_end:]
    cut = min(
        (i for i in (body.find("\n## Answer"), body.find("\n## Comments")) if i != -1),
        default=len(body),
    )
    main_part, rest = body[:cut], body[cut:]

    answer = ""
    a_m = re.search(r"\n## Answer\n(.*?)(?=\n## |\Z)", rest, re.S)
    if a_m and a_m.group(1).strip():
        answer = a_m.group(1).strip()

    comments = ""
    c_m = re.search(r"\n## Comments\n(.*)\Z", rest, re.S)
    if c_m and c_m.group(1).strip():
        comments = c_m.group(1).strip()

    return {
        "file": path.name,
        "num": int(path.name.split("-")[0]),
        "title": title,
        "type": ftype,
        "status": status,
        "blocked": blocked,
        "body": main_part.strip(),
        "answer": answer,
        "comments": comments,
    }


def patch_links(text: str) -> str:
    # research/ files -> moved into the "Материалы исследования" comment
    text = re.sub(
        r"— в файле\s*\n?\[`[^]]+\]\(\.\./research/[^)]+\)",
        "— в комментарии «Материалы исследования»",
        text,
    )
    # SVG moved to .scratch/spt-tank/
    text = text.replace(
        "](02-eskiz-komponovki-korpusa.svg)",
        "](.scratch/spt-tank/02-eskiz-komponovki-korpusa.svg)",
    )
    # Loose workspace notes stay in .scratch/spt-tank/
    text = text.replace(
        "](../intervyu-sertifikaciya.md)",
        "](.scratch/spt-tank/intervyu-sertifikaciya.md)",
    )
    text = text.replace("../pechat-odna-stranica-a4.html", "pechat-odna-stranica-a4.html")
    # Local tracker file pointers
    text = text.replace("(`map.md`, «Out of scope»)", "(карта усилия, раздел «Out of scope»)")
    text = text.replace(
        "(см. `issues/01-primenimaya-normativnaya-baza.md`)", "(см. тикет 01)"
    )
    return text


def main():
    tickets = sorted(
        (parse_ticket(p) for p in sorted(ROOT.glob("issues/*.md"))),
        key=lambda t: t["num"],
    )
    print(f"Parsed {len(tickets)} tickets")

    # --- 1. Map issue (placeholder body, patched after tickets exist) -------
    existing = gh(f"repos/{REPO}/issues?state=all&per_page=100")
    if any("wayfinder:map" in [l["name"] for l in i.get("labels", [])] for i in existing):
        sys.exit("Map issue already exists — aborting to avoid duplicates.")

    map_num = gh(
        f"repos/{REPO}/issues",
        {
            "title": "Карта: корпус СПТ — аналог станции подготовки топлива",
            "body": "Карта усилия `spt-tank`. Наполняется после миграции тикетов.",
            "labels": ["wayfinder:map"],
        },
    )["number"]
    print(f"Map issue: #{map_num}")

    # --- 2. Probe native dependencies ---------------------------------------
    _, deps_ok = try_gh(f"repos/{REPO}/issues/{map_num}/dependencies/blocked_by")
    print(f"Native dependencies: {'available' if deps_ok else 'NOT available — fallback to body lines'}")

    # --- 3. Tickets ----------------------------------------------------------
    mapping = {}  # local ticket num -> issue number
    for t in tickets:
        labels = [TYPE_LABEL.get(t["type"], "wayfinder:task")]
        if t["status"] != "resolved":
            labels.append("needs-triage")
        fallback = ""
        if not deps_ok and t["blocked"]:
            fallback = "Blocked by: " + ", ".join(f"#{mapping[b]}" for b in t["blocked"] if b in mapping) + "\n\n"
        body = (
            f"> Перенесено из локального трекера: `.scratch/spt-tank/issues/{t['file']}`\n\n"
            f"{fallback}{patch_links(t['body'])}\n\n"
            f"Type: `{t['type']}` · Status (на момент миграции): `{t['status']}`"
        )
        issue = gh(
            f"repos/{REPO}/issues",
            {"title": t["title"], "body": body, "labels": labels},
        )
        mapping[t["num"]] = issue["number"]
        print(f"  #{issue['number']} <- {t['file']} ({t['status']})")

        if t["answer"]:
            gh(f"repos/{REPO}/issues/{issue['number']}/comments",
               {"body": "## Ответ\n\n" + patch_links(t["answer"])})
        research = ROOT / "research" / t["file"]
        if research.exists():
            gh(f"repos/{REPO}/issues/{issue['number']}/comments",
               {"body": "## Материалы исследования\n\n<details><summary>Полный текст (перенесён из research/)</summary>\n\n"
                        + research.read_text(encoding="utf-8").strip() + "\n\n</details>"})
        if t["comments"]:
            gh(f"repos/{REPO}/issues/{issue['number']}/comments",
               {"body": "## Комментарии\n\n" + patch_links(t["comments"])})
        if t["status"] == "resolved":
            gh(f"repos/{REPO}/issues/{issue['number']}",
               {"state": "closed", "state_reason": "completed"}, method="PATCH")

    # --- 4. Attach tickets to the map as sub-issues --------------------------
    for t in tickets:
        db_id = gh(f"repos/{REPO}/issues/{mapping[t['num']]}")["id"]
        ok, _ = try_gh(f"repos/{REPO}/issues/{map_num}/sub_issues",
                       {"sub_issue_id": db_id}, method="POST")
        if not ok:
            print(f"  ! sub-issue attach failed for ticket {t['num']}")
    print("Sub-issues attached")

    # --- 5. Blocking edges ----------------------------------------------------
    if deps_ok:
        for t in tickets:
            for b in t["blocked"]:
                if b not in mapping:
                    continue
                blocker_id = gh(f"repos/{REPO}/issues/{mapping[b]}")["id"]
                ok, _ = try_gh(
                    f"repos/{REPO}/issues/{mapping[t['num']]}/dependencies/blocked_by",
                    {"issue_id": blocker_id}, method="POST")
                if ok:
                    print(f"  dep: #{mapping[t['num']]} blocked_by #{mapping[b]}")

    # --- 6. Final map body ----------------------------------------------------
    map_md = (ROOT / "map.md").read_text(encoding="utf-8")
    map_md = re.sub(r"^\`wayfinder:map\`.*$\n", "", map_md, flags=re.M)
    map_md = re.sub(
        r"\]\(issues/(\d+)-[^)]*\.md\)",
        lambda m: f"](#{mapping[int(m.group(1))]})",
        map_md,
    )
    map_md = re.sub(
        r"Детали: \`research/\d+-[^`]+\.md\`",
        lambda m: f"Детали: #{mapping[int(re.search(r'research/(\d+)-', m.group(0)).group(1))]}",
        map_md,
    )
    map_md = map_md.replace(
        "`issues/02-eskiz-komponovki-korpusa.svg`",
        "`.scratch/spt-tank/02-eskiz-komponovki-korpusa.svg`",
    )
    map_md = map_md.replace(
        "`research/13-sostav-i-parametry-stancii-po-referensu.md`",
        f"#{mapping[13]}",
    )
    map_md += (
        "\n---\n\n_Карта перенесена из `.scratch/spt-tank/map.md` (локальный трекер, "
        "удалён при миграции). Тикеты — sub-issues этой карты._\n"
    )
    gh(f"repos/{REPO}/issues/{map_num}", {"body": map_md}, method="PATCH")
    print("Map body patched")

    print("\nMapping (ticket -> issue):")
    for n in sorted(mapping):
        print(f"  {n:02d} -> #{mapping[n]}")


if __name__ == "__main__":
    main()
