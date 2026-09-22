#!/usr/bin/env python3
"""Regenerate reviewer-facing quantitative tables and Figures 2-3 from recomputed evidence."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def pct(x): return "n/a" if x is None else f"{100*float(x):.2f}"
def point(rep):
    s=next(iter(rep["systems"].values()))
    return s["summary"],s["confidence_intervals"]

def svg_escape(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--generated",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    args=ap.parse_args()
    g=args.generated; out=args.output_dir
    out.mkdir(parents=True,exist_ok=True)

    hist={p:load(g/f"historical-{p}.json") for p in ("gpt","claude")}
    final=load(g/"final-v2/mia-v2-regression-evaluation.json")
    b2={p:load(g/f"b2-{p}/evaluation.json") for p in ("gpt","claude")}
    b4m={p:load(g/f"b4-{p}/evaluation.json") for p in ("gpt","claude")}
    mech={p:load(g/f"mechanism-{p}/report.json") for p in ("gpt","claude")}
    comp={p:load(g/f"component-{p}.json") for p in ("gpt","claude")}
    topn=load(g/"topn.json")
    challenge=load(g/"challenge-v2.json")

    # Table 2: frozen historical matrix + final MIA.
    lines=[
      "# Regenerated paper quantitative tables","",
      "## Frozen test-benchmark results","",
      "| Family | System | UER % | CEC % | Macro-F1 % |",
      "| --- | --- | ---: | ---: | ---: |",
    ]
    table2={}
    for provider,label in (("gpt","GPT"),("claude","Claude")):
        table2[provider]={}
        for sid in ("b0","b1","b2","b3","b4"):
            s=hist[provider]["systems"][sid]["summary"]
            cec=None if sid=="b0" else s["correct_execution_coverage"]
            vals=(s["unsafe_execution_rate"],cec,s["action_macro_f1"])
            table2[provider][sid]={"uer":vals[0],"cec":vals[1],"macro_f1":vals[2]}
            lines.append(f"| {label} | {sid.upper()} | {pct(vals[0])} | {pct(vals[1])} | {pct(vals[2])} |")
        s=final["providers"][provider]["v2_summary"]
        vals=(s["unsafe_execution_rate"],s["correct_execution_coverage"],s["action_macro_f1"])
        table2[provider]["mia"]={"uer":vals[0],"cec":vals[1],"macro_f1":vals[2]}
        lines.append(f"| {label} | MIA | {pct(vals[0])} | {pct(vals[1])} | {pct(vals[2])} |")
    lines += ["","## Representation-matched mechanism controls","",
      "| Family | System | UER % | CEC % | Macro-F1 % |",
      "| --- | --- | ---: | ---: | ---: |"]
    table3={}
    for provider,label in (("gpt","GPT"),("claude","Claude")):
        table3[provider]={}
        for sid,rep in (("b2-matched",b2[provider]),("b4-matched",b4m[provider])):
            s,_=point(rep)
            vals=(s["unsafe_execution_rate"],s["correct_execution_coverage"],s["action_macro_f1"])
            table3[provider][sid]={"uer":vals[0],"cec":vals[1],"macro_f1":vals[2]}
            lines.append(f"| {label} | {sid.replace('-',' ').title().replace(' ','-')} | {pct(vals[0])} | {pct(vals[1])} | {pct(vals[2])} |")
        s=final["providers"][provider]["v2_summary"]
        vals=(s["unsafe_execution_rate"],s["correct_execution_coverage"],s["action_macro_f1"])
        table3[provider]["mia"]={"uer":vals[0],"cec":vals[1],"macro_f1":vals[2]}
        lines.append(f"| {label} | MIA | {pct(vals[0])} | {pct(vals[1])} | {pct(vals[2])} |")

    lines += ["","## Fixed-generation deterministic replay","",
      "| Variant | GPT UER % | Claude UER % |","| --- | ---: | ---: |"]
    replay={}
    variants=[
      ("Full MIA","full","mechanism"),
      ("No ambiguity margin","no-margin","mechanism"),
      ("No execution threshold","no-tau-e","mechanism"),
      ("No grain validation","drop-grain","mechanism"),
      ("All validators off","all-validators-off","component"),
      ("Grain validation only","grain-only","component"),
      ("Ignore unresolved slots","ignore-unresolved-slots","component"),
    ]
    for label,key,source in variants:
        vals={}
        for p in ("gpt","claude"):
            rep=mech[p]["summaries"][key] if source=="mechanism" else comp[p]["summaries"][key]
            vals[p]=rep["unsafe_execution_rate"]
        replay[key]=vals
        lines.append(f"| {label} | {pct(vals['gpt'])} | {pct(vals['claude'])} |")

    lines += ["","## Post-freeze challenge-v2","",
      "| Family | Action exact | UER | CEC | Reject exact |",
      "| --- | ---: | ---: | ---: | ---: |"]
    for p,label in (("gpt","GPT"),("claude","Claude")):
        x=challenge["providers"][p]
        lines.append(
          f"| {label} | {x['action_exact']['correct']}/{x['action_exact']['n']} | "
          f"{x['uer']['count']}/{x['uer']['n']} | "
          f"{x['cec']['correct']}/{x['cec']['n']} | "
          f"{x['reject_correct']['num']}/{x['reject_correct']['den']} |"
        )
    (out/"tables.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

    # Figure 2: controlled safety/coverage. Values and 95% intervals are taken only
    # from recomputed reports generated earlier in reproduce_paper.sh.
    panels=[]
    for p,label in (("gpt","GPT"),("claude","Claude")):
        pts=[]
        for sid in ("b1","b4"):
            x=hist[p]["systems"][sid]
            pts.append((sid.upper(),x["summary"],x["confidence_intervals"]))
        for sid,rep in (("B2-M",b2[p]),("B4-M",b4m[p])):
            s,ci=point(rep); pts.append((sid,s,ci))
        s=final["providers"][p]["v2_summary"]
        ci={
          "unsafe_execution_rate": final["providers"][p]["v2_bootstrap"]["unsafe_execution_rate"],
          "correct_execution_coverage": final["providers"][p]["v2_bootstrap"]["correct_execution_coverage"],
        }
        pts.append(("MIA",s,ci))
        panels.append((label,pts))

    W,H=1120,470
    sv=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#111}.axis{stroke:#444;stroke-width:1}.ci{stroke:#888;stroke-width:1.5}.pt{fill:#111}.hollow{fill:white;stroke:#555;stroke-width:2}</style>',
        '<text x="560" y="28" text-anchor="middle" font-size="20" font-weight="700">Controlled benchmark: unsafe execution vs correct execution coverage</text>']
    for pi,(label,pts) in enumerate(panels):
        x0=80+pi*550; y0=400; pw=430; ph=320
        sv += [f'<text x="{x0+pw/2}" y="60" text-anchor="middle" font-size="18" font-weight="700">{label}</text>',
               f'<line x1="{x0}" y1="{y0}" x2="{x0+pw}" y2="{y0}" class="axis"/>',
               f'<line x1="{x0}" y1="{y0-ph}" x2="{x0}" y2="{y0}" class="axis"/>']
        for t in range(0,6):
            xv=x0+pw*t/5
            sv.append(f'<text x="{xv}" y="{y0+22}" text-anchor="middle" font-size="12">{20*t}%</text>')
        for t in range(0,4):
            yv=y0-ph*t/3
            sv.append(f'<text x="{x0-8}" y="{yv+4}" text-anchor="end" font-size="12">{10*t}%</text>')
        for idx,(name,s,ci) in enumerate(pts):
            cec=float(s["correct_execution_coverage"]); uer=float(s["unsafe_execution_rate"])
            x=x0+pw*cec
            ycapped=min(uer,.30); y=y0-ph*(ycapped/.30)
            cci=ci.get("correct_execution_coverage")
            uci=ci.get("unsafe_execution_rate")
            if isinstance(cci,dict): clo,chi=cci["low"],cci["high"]
            else: clo,chi=cci
            if isinstance(uci,dict): ulo,uhi=uci["low"],uci["high"]
            else: ulo,uhi=uci
            xlo=x0+pw*float(clo); xhi=x0+pw*float(chi)
            ylo=y0-ph*(min(float(uhi),.30)/.30); yhi=y0-ph*(min(float(ulo),.30)/.30)
            sv += [f'<line x1="{xlo}" y1="{y}" x2="{xhi}" y2="{y}" class="ci"/>',
                   f'<line x1="{x}" y1="{ylo}" x2="{x}" y2="{yhi}" class="ci"/>']
            cls="hollow" if name in ("B1","B4") else "pt"
            sv.append(f'<circle cx="{x}" cy="{y}" r="{7 if name=="MIA" else 5}" class="{cls}"/>')
            sv.append(f'<text x="{x+9}" y="{y-7}" font-size="12">{svg_escape(name)} ({100*uer:.2f}%, {100*cec:.2f}%)</text>')
            if uer>.30:
                sv.append(f'<text x="{x+9}" y="{y+10}" font-size="11">UER off-scale: {100*uer:.2f}%</text>')
        paired=mech[p]["paired"]["mia_minus_b4_matched"]["unsafe_execution_rate"]
        sv += [
            f'<text x="{x0+pw/2}" y="92" text-anchor="middle" font-size="12">MIA - B4-M UER: {100*paired["estimate"]:+.2f} pp</text>',
            f'<text x="{x0+pw/2}" y="108" text-anchor="middle" font-size="11">95% paired CI: {100*paired["low"]:+.2f} to {100*paired["high"]:+.2f} pp</text>',
            f'<text x="{x0+pw/2}" y="455" text-anchor="middle" font-size="14">CEC</text>'
        ]
    sv.append('<text x="20" y="240" transform="rotate(-90 20 240)" text-anchor="middle" font-size="14">UER (axis capped at 30%)</text>')
    sv.append('</svg>')
    (out/"controlled-safety-coverage-final-mia.svg").write_text("\n".join(sv)+"\n",encoding="utf-8")

    # Figure 3: governed-error visibility after top-N exclusion.
    h2={p:topn["providers"][p]["h2_without_topn"] for p in ("gpt","claude")}
    W,H=760,320; x0=130; x1=700; maxg=max(v["groups_remaining"] for v in h2.values())
    sv=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#111}.axis{stroke:#444}.link{stroke:#999;stroke-width:5}.open{fill:white;stroke:#555;stroke-width:2}.solid{fill:#111}</style>',
        '<text x="380" y="28" text-anchor="middle" font-size="19" font-weight="700">Governed errors hidden by execution-result evaluation</text>',
        f'<line x1="{x0}" y1="270" x2="{x1}" y2="270" class="axis"/>']
    for t in range(0,5):
        val=maxg*t/4; x=x0+(x1-x0)*val/maxg
        sv.append(f'<text x="{x}" y="292" text-anchor="middle" font-size="12">{int(round(val))}</text>')
    for i,(p,label) in enumerate((("gpt","GPT"),("claude","Claude"))):
        y=110+i*100; e=h2[p]["execution_visible_groups"]; it=h2[p]["intent_visible_groups"]
        xe=x0+(x1-x0)*e/maxg; xi=x0+(x1-x0)*it/maxg
        sv += [f'<text x="{x0-20}" y="{y+5}" text-anchor="end" font-size="16" font-weight="700">{label}</text>',
               f'<line x1="{xe}" y1="{y}" x2="{xi}" y2="{y}" class="link"/>',
               f'<circle cx="{xe}" cy="{y}" r="7" class="open"/>',
               f'<circle cx="{xi}" cy="{y}" r="7" class="solid"/>',
               f'<text x="{xe}" y="{y-15}" text-anchor="middle" font-size="13">{e}</text>',
               f'<text x="{xi}" y="{y-15}" text-anchor="middle" font-size="13">{it}</text>',
               f'<text x="{(xe+xi)/2}" y="{y+28}" text-anchor="middle" font-size="12">+{it-e} groups ({100*h2[p]["visibility_gain"]:.2f} pp)</text>']
    sv.append('</svg>')
    (out/"hidden-intent-errors.svg").write_text("\n".join(sv)+"\n",encoding="utf-8")

    values={"table2":table2,"table3":table3,"replay":replay,
            "matched_assurer_effect":{p:mech[p]["paired"]["mia_minus_b4_matched"] for p in ("gpt","claude")},
            "h2_without_topn":{p:{
              "groups":h2[p]["groups_remaining"],
              "execution_visible":h2[p]["execution_visible_groups"],
              "intent_visible":h2[p]["intent_visible_groups"],
              "gain":h2[p]["visibility_gain"],
              "ci":h2[p]["bootstrap_95"]
            } for p in ("gpt","claude")}}
    (out/"paper-assets-values.json").write_text(json.dumps(values,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":"pass","tables":"tables.md","figures":["controlled-safety-coverage-final-mia.svg","hidden-intent-errors.svg"]},sort_keys=True))

if __name__=="__main__": main()
