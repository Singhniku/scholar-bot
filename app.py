"""
Scholar-Bot Streamlit Web UI
Run: streamlit run app.py
"""
import base64
import io
import json
import logging
import os
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Scholar-Bot | ATS Resume Optimizer",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.main-header{font-size:2.4rem;font-weight:700;color:#1e3a5f;margin-bottom:0.2rem}
.sub-header{font-size:1rem;color:#555;margin-bottom:1.5rem}
.job-card{border:1px solid #e0e6f0;border-radius:10px;padding:1rem 1.2rem;
          margin-bottom:0.7rem;background:#fafcff}
.job-card:hover{border-color:#2d6a9f;background:#f0f6ff}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;
       font-size:.75rem;font-weight:600;margin:2px}
.badge-green{background:#d4edda;color:#155724}
.badge-blue{background:#cce5ff;color:#004085}
.badge-orange{background:#fff3cd;color:#856404}
.badge-red{background:#f8d7da;color:#721c24}
.badge-purple{background:#e2d9f3;color:#432874}
.apply-status-done{color:#155724;font-weight:700}
.apply-status-fail{color:#721c24;font-weight:700}
.apply-status-wait{color:#856404;font-weight:700}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def score_badge(score: float) -> str:
    if score >= 80:
        return f'<span class="badge badge-green">Excellent {score:.0f}%</span>'
    elif score >= 60:
        return f'<span class="badge badge-blue">Good {score:.0f}%</span>'
    elif score >= 40:
        return f'<span class="badge badge-orange">Fair {score:.0f}%</span>'
    return f'<span class="badge badge-red">Low {score:.0f}%</span>'


def fmt_date(dt) -> str:
    if not dt:
        return "Unknown"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%b %d, %Y")


@st.cache_resource
def get_ai_client(provider: str, google_key: str, anthropic_key: str):
    from src.ai_client import AIClient
    return AIClient.from_keys(
        provider=provider,
        google_key=google_key,
        anthropic_key=anthropic_key,
    )


@st.cache_resource
def get_extractor(provider: str, google_key: str, anthropic_key: str):
    from src.skills_extractor import SkillsExtractor
    client = get_ai_client(provider, google_key, anthropic_key)
    return SkillsExtractor(client=client)


@st.cache_resource
def get_optimizer(provider: str, google_key: str, anthropic_key: str):
    from src.ats_optimizer import ATSOptimizer
    client = get_ai_client(provider, google_key, anthropic_key)
    return ATSOptimizer(client=client)


# ── Session state init ────────────────────────────────────────────────────────
_STATE_DEFAULTS = {
    "resume_text": None,
    "resume_data": None,
    "jobs": None,
    "ranked_jobs": None,
    "top_optimized": None,
    # auto-apply
    "apply_queue": [],          # list of job dicts selected for apply
    "apply_results": [],        # filled by background thread
    "apply_status_map": {},     # job_id -> status string
    "apply_screenshot_map": {}, # job_id -> base64 PNG
    "apply_thread_running": False,
    "applier": None,
    # pdf paths for each optimized resume (keyed by job_id)
    "opt_pdf_paths": {},
}
for k, v in _STATE_DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ AI Provider")

    ai_provider = st.selectbox(
        "Provider",
        options=["gemini", "anthropic"],
        index=0 if os.getenv("AI_PROVIDER", "gemini") == "gemini" else 1,
        format_func=lambda p: {
            "gemini":    "Google Gemini (FREE)",
            "anthropic": "Anthropic Claude (Paid)",
        }[p],
    )

    if ai_provider == "gemini":
        google_key = st.text_input(
            "Google API Key",
            value=os.getenv("GOOGLE_API_KEY", ""),
            type="password",
            help="Free at aistudio.google.com → Get API key",
        )
        anthropic_key = ""
        active_key = google_key
        if google_key:
            st.caption("Model: gemini-1.5-flash · Free tier")
    else:
        anthropic_key = st.text_input(
            "Anthropic API Key",
            value=os.getenv("ANTHROPIC_API_KEY", ""),
            type="password",
            help="console.anthropic.com/settings/billing",
        )
        google_key = ""
        active_key = anthropic_key
        if anthropic_key:
            st.caption("Model: claude-sonnet-4-6")

    st.divider()
    st.markdown("### 🔍 Job Search")
    location     = st.text_input("Location", value=os.getenv("DEFAULT_LOCATION", "United States"))
    num_jobs     = st.slider("Max Jobs", 10, 100, 50, 10)
    days_filter  = st.selectbox(
        "Posted Within", [1, 7, 30], index=2,
        format_func=lambda d: {1:"24 h",7:"1 week",30:"1 month"}[d]
    )
    optimize_top = st.slider("Optimise For Top N Jobs", 1, 5, 3)

    st.divider()
    st.markdown("### 🤖 Auto-Apply (LinkedIn)")
    li_email    = st.text_input("LinkedIn Email",    value=os.getenv("LINKEDIN_EMAIL",""))
    li_password = st.text_input("LinkedIn Password", value=os.getenv("LINKEDIN_PASSWORD",""), type="password")
    headless    = st.checkbox("Headless browser (no window)", value=False,
                              help="Uncheck to see the browser while it fills forms")

    st.divider()
    provider_label = "Google Gemini (free)" if ai_provider == "gemini" else "Anthropic Claude"
    st.caption(f"Scholar-Bot v1.0 · {provider_label}")


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="main-header">🎓 Scholar-Bot</div>'
    '<div class="sub-header">AI-powered ATS resume optimizer + LinkedIn job matcher + auto-apply</div>',
    unsafe_allow_html=True,
)


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_upload, tab_jobs, tab_resume, tab_apply, tab_report = st.tabs([
    "📄 Upload Resume",
    "💼 Job Matches",
    "✏️ Optimized Resumes",
    "🚀 Auto Apply",
    "📊 Report",
])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — Upload & Run Pipeline
# ═════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.markdown("#### Upload your resume")
    uploaded = st.file_uploader(
        "Drag & drop (.pdf .jpg .jpeg .png .svg)",
        type=["pdf","jpg","jpeg","png","svg"],
    )

    c1, c2 = st.columns(2)
    run_full     = c1.button("🚀 Full Pipeline (Parse → Match → Optimise)",
                             type="primary", disabled=not(uploaded and active_key),
                             use_container_width=True)
    run_analysis = c2.button("🔬 Resume Analysis Only",
                             disabled=not(uploaded and active_key),
                             use_container_width=True)

    if not active_key:
        st.warning(
            "Enter your API key in the sidebar.  "
            "**Google Gemini is free** — get a key at [aistudio.google.com](https://aistudio.google.com)."
        )

    if (run_full or run_analysis) and uploaded and active_key:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        try:
            # Step 1 — Parse
            with st.status("Parsing resume…", expanded=True) as s:
                from src.resume_parser import ResumeParser
                st.write("Extracting text…")
                text = ResumeParser().parse(tmp_path)
                if not text.strip():
                    st.error("No text extracted — try a clearer scan or PDF.")
                    st.stop()
                st.session_state.resume_text = text
                s.update(label=f"Parsed ({len(text):,} chars)", state="complete")

            # Step 2 — Extract skills
            with st.status(f"Extracting skills with {provider_label}…", expanded=True) as s:
                ext = get_extractor(ai_provider, google_key, anthropic_key)
                rd  = ext.extract_from_resume(text)
                st.session_state.resume_data = rd
                skills = (rd.get("technical_skills",[])
                          + rd.get("tools",[])
                          + rd.get("frameworks",[]))
                s.update(label=f"Found {len(skills)} skills", state="complete")

            if run_full:
                # Step 3 — Scrape LinkedIn
                with st.status(f"Searching LinkedIn ({location}, {days_filter}d)…",
                               expanded=True) as s:
                    from src.linkedin_scraper import LinkedInScraper
                    jobs = LinkedInScraper().search_jobs(
                        keywords=skills[:10], location=location,
                        num_jobs=num_jobs, days=days_filter)
                    st.session_state.jobs = jobs
                    s.update(label=f"Retrieved {len(jobs)} job listings", state="complete")

                if not jobs:
                    st.warning("No jobs returned. LinkedIn may be rate-limiting — wait a few minutes.")
                    st.stop()

                # Step 4 — Score
                with st.status("Scoring job matches…", expanded=True) as s:
                    ranked, prog = [], st.progress(0)
                    jobs_with_desc = [j for j in jobs if j.get("description")]
                    for i, job in enumerate(jobs_with_desc):
                        reqs = ext.extract_from_job(job["description"], job.get("title",""))
                        analysis = ext.calculate_match_score(rd, reqs)
                        ranked.append({"job": job, "job_requirements": reqs,
                                       "match_analysis": analysis,
                                       "match_score": analysis.get("score", 0)})
                        prog.progress((i+1)/len(jobs_with_desc))
                    ranked.sort(
                        key=lambda x: (
                            x["job"].get("posted_date") or datetime.min,
                            x["match_score"],
                        ), reverse=True)
                    st.session_state.ranked_jobs = ranked
                    s.update(label=f"Scored {len(ranked)} jobs — best: "
                             f"{ranked[0]['match_score']:.1f}% {ranked[0]['job']['title']}",
                             state="complete")

                # Step 5 — Optimise resumes
                with st.status(f"Optimising resumes for top {optimize_top} jobs…",
                               expanded=True) as s:
                    opt = get_optimizer(ai_provider, google_key, anthropic_key)
                    top = opt.bulk_optimize(rd, ranked, top_n=optimize_top)
                    st.session_state.top_optimized = top

                    # Pre-generate PDFs so auto-apply tab can upload them
                    from src.resume_generator import ResumeGenerator
                    gen = ResumeGenerator()
                    pdf_paths = {}
                    for item in top:
                        jid = item["job"].get("job_id","") or item["job"].get("title","")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tp:
                            gen.generate_pdf(item["optimized_resume"], tp.name)
                            pdf_paths[jid] = tp.name
                    st.session_state.opt_pdf_paths = pdf_paths
                    s.update(label=f"Generated {len(top)} optimised resumes", state="complete")

            st.success("Done! Check the other tabs.")

        finally:
            os.unlink(tmp_path)

    # Skills snapshot
    if st.session_state.resume_data:
        rd = st.session_state.resume_data
        st.divider()
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Name",  rd.get("name","—"))
        c2.metric("Role",  rd.get("current_title","—"))
        c3.metric("Exp",   f"{rd.get('experience_years','?')} yrs")
        c4.metric("Location", rd.get("location","—"))

        all_skills = list(dict.fromkeys(
            rd.get("technical_skills",[]) + rd.get("frameworks",[]) + rd.get("tools",[])))
        if all_skills:
            st.markdown("**Skills detected**")
            st.markdown(
                " ".join(f'<span class="badge badge-blue">{s}</span>' for s in all_skills),
                unsafe_allow_html=True)
        if rd.get("summary"):
            st.info(rd["summary"])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — Job Matches
# ═════════════════════════════════════════════════════════════════════════════
with tab_jobs:
    if not st.session_state.ranked_jobs:
        st.info("Run the full pipeline in **Upload Resume** to see job matches.")
    else:
        ranked = st.session_state.ranked_jobs

        c1,c2,c3 = st.columns([1,1,2])
        min_score = c1.slider("Min Match %", 0, 100, 0, key="minscore")
        show_n    = c2.selectbox("Show Top", [10,25,50,100], index=1)
        search_q  = c3.text_input("Filter title / company", "")

        filtered = [
            r for r in ranked
            if r["match_score"] >= min_score
            and (not search_q
                 or search_q.lower() in r["job"].get("title","").lower()
                 or search_q.lower() in r["job"].get("company","").lower())
        ][:show_n]

        if filtered:
            avg = sum(r["match_score"] for r in filtered)/len(filtered)
            m1,m2,m3 = st.columns(3)
            m1.metric("Jobs", len(ranked))
            m2.metric("Avg Match", f"{avg:.1f}%")
            m3.metric("Best", f"{max(r['match_score'] for r in filtered):.1f}%")

        st.divider()

        for r in filtered:
            job = r["job"]; analysis = r["match_analysis"]; score = r["match_score"]
            st.markdown(
                f'<div class="job-card">'
                f'<b style="font-size:1.05rem">{job.get("title","")}</b>&nbsp;'
                f'{score_badge(score)}<br>'
                f'🏢 {job.get("company","")}&nbsp;&nbsp;'
                f'📍 {job.get("location","")}&nbsp;&nbsp;'
                f'📅 {fmt_date(job.get("posted_date"))}'
                f'</div>',
                unsafe_allow_html=True)
            with st.expander("Details & Skills Gap"):
                ca,cb = st.columns(2)
                with ca:
                    st.markdown("**Matching Skills**")
                    st.markdown(
                        " ".join(f'<span class="badge badge-green">{s}</span>'
                                 for s in analysis.get("matched_required",[])),
                        unsafe_allow_html=True)
                with cb:
                    st.markdown("**Missing Required Skills**")
                    st.markdown(
                        " ".join(f'<span class="badge badge-red">{s}</span>'
                                 for s in analysis.get("missing_required",[])),
                        unsafe_allow_html=True)
                if job.get("url"):
                    st.link_button("View on LinkedIn →", job["url"])

        # Add selected jobs to apply queue
        st.divider()
        st.markdown("#### Select jobs to auto-apply")
        selections = []
        for r in filtered[:20]:
            job = r["job"]
            label = f"{job.get('title','?')} @ {job.get('company','?')} — {r['match_score']:.0f}%"
            if st.checkbox(label, key=f"sel_{job.get('job_id',job.get('title',''))}"):
                selections.append(job)

        if st.button("Add Selected to Apply Queue", type="primary",
                     disabled=not selections):
            existing_ids = {j.get("job_id") for j in st.session_state.apply_queue}
            new = [j for j in selections if j.get("job_id") not in existing_ids]
            st.session_state.apply_queue.extend(new)
            st.success(f"Added {len(new)} jobs to the apply queue. Go to the **Auto Apply** tab.")

        if filtered:
            export = [{"rank":i+1,"title":r["job"].get("title"),
                       "company":r["job"].get("company"),"location":r["job"].get("location"),
                       "posted_date":fmt_date(r["job"].get("posted_date")),
                       "match_score":r["match_score"],"url":r["job"].get("url")}
                      for i,r in enumerate(filtered)]
            st.download_button("Download Job List (JSON)", json.dumps(export,indent=2),
                               "jobs.json","application/json")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — Optimized Resumes
# ═════════════════════════════════════════════════════════════════════════════
with tab_resume:
    if not st.session_state.top_optimized:
        st.info("Run the full pipeline to generate ATS-optimised resumes.")
    else:
        from src.resume_generator import ResumeGenerator
        gen = ResumeGenerator()

        for i, item in enumerate(st.session_state.top_optimized, 1):
            job = item["job"]; opt = item["optimized_resume"]; score = item.get("match_score",0)
            st.markdown(
                f"#### {i}. {job.get('title')} — {job.get('company')} {score_badge(score)}",
                unsafe_allow_html=True)

            ca,cb = st.columns(2)
            with ca:
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tp:
                        gen.generate_pdf(opt, tp.name)
                        pdf_bytes = Path(tp.name).read_bytes()
                        os.unlink(tp.name)
                    st.download_button(
                        f"⬇ Download PDF #{i}",
                        pdf_bytes,
                        f"resume_{job.get('company','').replace(' ','_')[:12]}_{i}.pdf",
                        "application/pdf", key=f"pdf_{i}", use_container_width=True, type="primary")
                except Exception as e:
                    st.error(f"PDF error: {e}")

            with cb:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w") as tm:
                    gen.generate_markdown(opt, tm.name)
                    md_text = Path(tm.name).read_text()
                    os.unlink(tm.name)
                st.download_button(
                    f"⬇ Download Markdown #{i}", md_text,
                    f"resume_{job.get('company','').replace(' ','_')[:12]}_{i}.md",
                    "text/markdown", key=f"md_{i}", use_container_width=True)

            with st.expander("Preview"):
                c1,c2 = st.columns([2,1])
                with c1:
                    st.markdown(f"**Summary:** {opt.get('summary','')}")
                    all_sk = list(dict.fromkeys(
                        opt.get("technical_skills",[]) + opt.get("frameworks",[]) + opt.get("tools",[])))
                    st.markdown(
                        " ".join(f'<span class="badge badge-blue">{s}</span>' for s in all_sk),
                        unsafe_allow_html=True)
                    for exp in opt.get("experience",[])[:2]:
                        st.markdown(f"**{exp.get('title')}** @ {exp.get('company')} *{exp.get('duration')}*")
                        for a in exp.get("achievements",[])[:2]:
                            st.markdown(f"- {a}")
                with c2:
                    st.markdown("**Changes made**")
                    for n in opt.get("optimization_notes",[])[:5]:
                        st.markdown(f"✓ {n}")
                    st.markdown("**Added keywords**")
                    st.markdown(
                        " ".join(f'<span class="badge badge-green">{k}</span>'
                                 for k in opt.get("added_keywords",[])[:8]),
                        unsafe_allow_html=True)
            st.divider()


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — Auto Apply
# ═════════════════════════════════════════════════════════════════════════════
with tab_apply:
    st.markdown("### 🚀 Auto Apply")
    st.markdown(
        "Scholar-Bot will open LinkedIn, pre-fill every Easy Apply form, "
        "then **pause for your review** before submitting. "
        "You only need to check the form and click **Submit** here."
    )

    if not li_email or not li_password:
        st.warning("Enter your LinkedIn credentials in the sidebar to use auto-apply.")

    queue = st.session_state.apply_queue

    if not queue:
        st.info(
            "No jobs in the apply queue. "
            "Go to **Job Matches**, tick the jobs you want, and click *Add Selected to Apply Queue*."
        )
    else:
        st.markdown(f"**{len(queue)} job(s) in queue:**")
        to_remove = []
        for j in queue:
            cc1, cc2 = st.columns([5,1])
            cc1.markdown(f"• **{j.get('title')}** @ {j.get('company')} — {j.get('location','')}")
            if cc2.button("Remove", key=f"rm_{j.get('job_id',j.get('title',''))}"):
                to_remove.append(j)
        for j in to_remove:
            st.session_state.apply_queue.remove(j)
        if to_remove:
            st.rerun()

        st.divider()

        resume_data = st.session_state.resume_data
        opt_pdfs    = st.session_state.opt_pdf_paths

        # Pick the best matching optimised PDF for each job, or use first available
        def pick_pdf(job: dict) -> str:
            jid = job.get("job_id","")
            if jid and jid in opt_pdfs:
                return opt_pdfs[jid]
            return next(iter(opt_pdfs.values()), "") if opt_pdfs else ""

        can_start = (
            li_email and li_password and resume_data
            and not st.session_state.apply_thread_running
        )

        if st.button("▶ Start Auto Apply", type="primary", disabled=not can_start):
            if not resume_data:
                st.error("Run the full pipeline first so Scholar-Bot has your resume data.")
            else:
                from src.auto_apply import AutoApply, ApplicationStatus

                status_map     = {}
                screenshot_map = {}
                results        = []

                def on_status(job_id: str, status: str, screenshot: Optional[str]):
                    status_map[job_id] = status
                    if screenshot:
                        screenshot_map[job_id] = screenshot
                    st.session_state.apply_status_map     = dict(status_map)
                    st.session_state.apply_screenshot_map = dict(screenshot_map)

                pdf_path = pick_pdf(queue[0])

                applier = AutoApply(
                    email=li_email, password=li_password,
                    resume_data=resume_data, resume_pdf_path=pdf_path,
                    headless=headless, on_status=on_status,
                )
                st.session_state.applier = applier

                def run_apply():
                    st.session_state.apply_thread_running = True
                    res = applier.apply_to_jobs(queue)
                    st.session_state.apply_results = res
                    st.session_state.apply_thread_running = False

                t = threading.Thread(target=run_apply, daemon=True)
                t.start()
                st.info("Auto-apply started in background. Review the status below.")

        # ── Live status panel ────────────────────────────────────────────────
        if st.session_state.apply_thread_running or st.session_state.apply_results:
            st.divider()
            st.markdown("#### Application Status")

            status_map     = st.session_state.apply_status_map
            screenshot_map = st.session_state.apply_screenshot_map
            applier        = st.session_state.applier

            for job in queue:
                jid   = job.get("job_id","")
                title = job.get("title","")
                comp  = job.get("company","")
                status = status_map.get(jid, "pending")

                # Colour-code status
                colour = {"done":"#155724","failed":"#721c24",
                          "waiting_approval":"#856404"}.get(status,"#004085")
                st.markdown(
                    f'<b style="color:{colour}">{title} @ {comp}</b> — '
                    f'<code>{status.replace("_"," ").upper()}</code>',
                    unsafe_allow_html=True)

                # Waiting for approval — show screenshot + approve/skip buttons
                if status == "waiting_approval" and applier:
                    if jid in screenshot_map:
                        img_bytes = base64.b64decode(screenshot_map[jid])
                        st.image(img_bytes, caption="Application Preview (pre-submission)",
                                 use_container_width=True)

                    st.markdown(
                        "**Review the form above. Click Submit to apply, or Skip to skip this job.**"
                    )
                    bc1, bc2 = st.columns(2)
                    if bc1.button("✅ Submit Application",
                                  key=f"submit_{jid}", type="primary"):
                        applier.signal_submit(approve=True)
                        st.success("Submitted! Moving to next job…")
                    if bc2.button("⏭ Skip This Job",
                                  key=f"skip_{jid}"):
                        applier.signal_submit(approve=False)
                        st.info("Skipped.")

            # Completed results
            if st.session_state.apply_results:
                st.divider()
                st.markdown("#### Completed")
                for r in st.session_state.apply_results:
                    icon = {"done":"✅","failed":"❌","skipped":"⏭"}.get(r.get("status",""),"•")
                    st.markdown(
                        f"{icon} **{r.get('title')} @ {r.get('company')}** — "
                        f"{r.get('status','').upper()}"
                        + (f" _{r.get('error','')} _" if r.get("error") else "")
                    )

            if st.session_state.apply_thread_running:
                st.info("Applying… refresh the page to see updates.")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 — Full Report
# ═════════════════════════════════════════════════════════════════════════════
with tab_report:
    if not st.session_state.ranked_jobs:
        st.info("Run the full pipeline to generate the report.")
    else:
        ranked = st.session_state.ranked_jobs
        st.markdown(f"### Full Report — {len(ranked)} jobs analysed")

        try:
            import pandas as pd
            scores = [r["match_score"] for r in ranked]
            buckets = {
                "Excellent (≥80%)": sum(1 for s in scores if s >= 80),
                "Good (60-79%)":    sum(1 for s in scores if 60 <= s < 80),
                "Fair (40-59%)":    sum(1 for s in scores if 40 <= s < 60),
                "Low (<40%)":       sum(1 for s in scores if s < 40),
            }
            st.bar_chart(pd.DataFrame({"Category":list(buckets.keys()),
                                        "Count":list(buckets.values())}).set_index("Category"))

            rows = [{"#":i,"Title":r["job"].get("title",""),
                     "Company":r["job"].get("company",""),
                     "Location":r["job"].get("location",""),
                     "Posted":fmt_date(r["job"].get("posted_date")),
                     "Match %":f"{r['match_score']:.1f}",
                     "URL":r["job"].get("url","")}
                    for i,r in enumerate(ranked,1)]
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button(
                "Download CSV", df.to_csv(index=False),
                "scholar_bot_report.csv","text/csv")
        except Exception as e:
            st.error(f"Table error: {e}")
