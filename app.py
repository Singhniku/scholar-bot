"""
Scholar-Bot Streamlit Web UI
Run: streamlit run app.py
"""
import base64
import json
import logging
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Scholar-Bot | ATS Resume Optimizer",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.main-header{font-size:2.4rem;font-weight:700;color:#1e3a5f;margin-bottom:0.1rem}
.sub-header{font-size:1rem;color:#666;margin-bottom:1.2rem}
.job-card{border:1px solid #dce6f5;border-radius:12px;padding:1rem 1.2rem;
          margin-bottom:0.8rem;background:#fafcff;transition:border .2s}
.job-card:hover{border-color:#2d6a9f;background:#f0f6ff}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;
       font-size:.75rem;font-weight:600;margin:2px}
.badge-green {background:#d4edda;color:#155724}
.badge-blue  {background:#cce5ff;color:#004085}
.badge-orange{background:#fff3cd;color:#856404}
.badge-red   {background:#f8d7da;color:#721c24}
.badge-grey  {background:#e9ecef;color:#495057}
.warn-box{background:#fff8e1;border-left:4px solid #ffc107;
          border-radius:6px;padding:0.7rem 1rem;margin-bottom:1rem;font-size:.9rem}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def score_badge(score: float, fallback: bool = False) -> str:
    tag = " (keyword)" if fallback else ""
    if score >= 80:
        return f'<span class="badge badge-green">Excellent {score:.0f}%{tag}</span>'
    elif score >= 60:
        return f'<span class="badge badge-blue">Good {score:.0f}%{tag}</span>'
    elif score >= 40:
        return f'<span class="badge badge-orange">Fair {score:.0f}%{tag}</span>'
    return f'<span class="badge badge-red">Low {score:.0f}%{tag}</span>'


def fmt_date(dt) -> str:
    if not dt:
        return "Unknown"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%b %d, %Y")


def _ai_available(provider: str, google_key: str, anthropic_key: str) -> bool:
    return bool(google_key if provider == "gemini" else anthropic_key)


# ── ATS audit ─────────────────────────────────────────────────────────────────
_ATS_SYSTEM = (
    "You are a senior ATS (Applicant Tracking System) expert. "
    "Score resumes and give precise, actionable improvement suggestions. "
    "Respond with valid JSON only — no markdown fences."
)

_ATS_KEYWORD_RULES = [
    ("contact_info",   "Has name + email + phone",          20),
    ("summary",        "Has professional summary/objective", 15),
    ("skills_section", "Has dedicated skills section",       15),
    ("experience",     "Has work experience with bullets",   20),
    ("education",      "Has education section",              10),
    ("keywords",       "Contains 10+ technical keywords",    10),
    ("length",         "Resume length 400-1200 words",       10),
]

def _ats_audit_keyword(text: str, rd: dict) -> dict[str, Any]:
    """Keyword-only ATS audit — no AI call."""
    checks, score = {}, 0
    word_count = len(text.split())

    rules_result = {
        "contact_info":   bool(rd.get("email") and rd.get("phone")),
        "summary":        bool(rd.get("summary") and len(rd.get("summary","")) > 30),
        "skills_section": len(rd.get("technical_skills",[])) > 0,
        "experience":     len(rd.get("experience",[])) > 0 or
                          any(k in text.lower() for k in ["experience","worked at","company"]),
        "education":      len(rd.get("education",[])) > 0 or
                          any(k in text.lower() for k in ["degree","university","college","b.s","m.s","phd"]),
        "keywords":       len(rd.get("all_keywords",[])) >= 10,
        "length":         400 <= word_count <= 1200,
    }

    suggestions, passed = [], []
    for key, label, pts in _ATS_KEYWORD_RULES:
        if rules_result[key]:
            score += pts
            passed.append(label)
        else:
            _suggestion_map = {
                "contact_info":   "Add your email and phone number clearly at the top.",
                "summary":        "Add a 2-4 sentence professional summary highlighting key skills.",
                "skills_section": "Add a dedicated 'Skills' section with your technical skills.",
                "experience":     "Add work experience with company name, title, dates, and bullet points.",
                "education":      "Add your education — degree, institution, year.",
                "keywords":       "Add more relevant technical keywords to pass ATS filters.",
                "length":         f"Resume is {word_count} words — ideal range is 400-1200 words.",
            }
            suggestions.append(_suggestion_map[key])

    return {
        "score": score,
        "passed": passed,
        "suggestions": suggestions,
        "word_count": word_count,
        "mode": "keyword",
        "ai_suggestions": [],
    }


def _ats_audit(text: str, rd: dict, has_ai: bool,
               ai_provider: str, google_key: str, anthropic_key: str) -> dict[str, Any]:
    """Full ATS audit — AI-powered when available, keyword fallback otherwise."""
    base = _ats_audit_keyword(text, rd)

    if not has_ai:
        return base

    try:
        client = _get_ai_client(ai_provider, google_key, anthropic_key)
        prompt = f"""Analyse this resume for ATS compliance and return JSON:
{{
  "ats_score": 0-100,
  "format_issues": ["issue 1", "issue 2"],
  "missing_sections": ["section 1"],
  "keyword_gaps": ["missing keyword 1"],
  "weak_bullets": ["original bullet → suggested rewrite"],
  "summary_suggestion": "improved summary text",
  "top_improvements": ["most impactful change 1", "most impactful change 2", "most impactful change 3"]
}}

Resume text (first 3000 chars):
{text[:3000]}"""
        resp = client.generate(_ATS_SYSTEM, prompt, max_tokens=1500)
        resp = resp.strip()
        if resp.startswith("```"):
            lines = resp.split("\n")
            resp = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        ai_result = json.loads(resp)
        base["score"]           = ai_result.get("ats_score", base["score"])
        base["ai_suggestions"]  = ai_result.get("top_improvements", [])
        base["format_issues"]   = ai_result.get("format_issues", [])
        base["missing_sections"]= ai_result.get("missing_sections", [])
        base["keyword_gaps"]    = ai_result.get("keyword_gaps", [])
        base["weak_bullets"]    = ai_result.get("weak_bullets", [])
        base["summary_suggestion"] = ai_result.get("summary_suggestion", "")
        base["mode"]            = "ai"
    except Exception as e:
        logger.warning(f"AI ATS audit failed, using keyword score: {e}")

    return base


@st.cache_resource
def _get_ai_client(provider: str, google_key: str, anthropic_key: str):
    from src.ai_client import AIClient
    return AIClient.from_keys(provider=provider, google_key=google_key,
                               anthropic_key=anthropic_key)


@st.cache_resource
def _get_extractor(provider: str, google_key: str, anthropic_key: str):
    from src.skills_extractor import SkillsExtractor
    return SkillsExtractor(client=_get_ai_client(provider, google_key, anthropic_key))


@st.cache_resource
def _get_optimizer(provider: str, google_key: str, anthropic_key: str):
    from src.ats_optimizer import ATSOptimizer
    return ATSOptimizer(client=_get_ai_client(provider, google_key, anthropic_key))


# ── Session state ─────────────────────────────────────────────────────────────
for k, v in {
    "resume_text": None, "resume_data": None, "ai_used": False,
    "jobs": None, "ranked_jobs": None, "top_optimized": None,
    "opt_pdf_paths": {}, "per_job_opt": {},
    "apply_queue": [], "apply_results": [], "apply_status_map": {},
    "apply_screenshot_map": {}, "apply_thread_running": False, "applier": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ AI Provider")
    ai_provider = st.selectbox(
        "Provider",
        options=["gemini", "anthropic"],
        index=0 if os.getenv("AI_PROVIDER", "gemini") == "gemini" else 1,
        format_func=lambda p: {"gemini": "Google Gemini (FREE)",
                                "anthropic": "Anthropic Claude (Paid)"}[p],
    )
    if ai_provider == "gemini":
        google_key    = st.text_input("Google API Key",
                                       value=os.getenv("GOOGLE_API_KEY", ""),
                                       type="password",
                                       help="Free at aistudio.google.com")
        anthropic_key = ""
        active_key    = google_key
        if google_key:
            st.caption("Model: gemini-2.5-flash · Free tier")
    else:
        anthropic_key = st.text_input("Anthropic API Key",
                                       value=os.getenv("ANTHROPIC_API_KEY", ""),
                                       type="password")
        google_key = ""
        active_key = anthropic_key
        if anthropic_key:
            st.caption("Model: claude-sonnet-4-6")

    st.divider()
    st.markdown("### 🔍 Job Search")
    job_title    = st.text_input("Job Title to Search",
                                  placeholder="e.g. Software Engineer, Data Scientist",
                                  help="LinkedIn will be searched for this exact title. "
                                       "Leave blank to search by resume skills only.")
    location     = st.text_input("Location", value=os.getenv("DEFAULT_LOCATION","United States"))
    num_jobs     = st.slider("Max Jobs to Fetch", 10, 100, 50, 10)
    min_match_pct= st.slider("Min Skill Match %", 10, 90, 50, 5,
                              help="Only show jobs where ≥ this % of required skills match your resume")
    days_filter  = st.number_input(
                        "Posted Within (days)", min_value=1, max_value=365,
                        value=30, step=1,
                        help="Show only jobs posted within this many days (1 = last 24 h)")
    optimize_top = st.slider("Auto-optimise Top N Jobs", 1, 5, 3)

    st.divider()
    st.markdown("### 🤖 Auto-Apply")
    li_email    = st.text_input("LinkedIn Email",    value=os.getenv("LINKEDIN_EMAIL",""))
    li_password = st.text_input("LinkedIn Password", value=os.getenv("LINKEDIN_PASSWORD",""),
                                 type="password")
    headless    = st.checkbox("Headless browser", value=False)
    st.divider()
    st.caption(f"Scholar-Bot v1.0 · {'Gemini (free)' if ai_provider=='gemini' else 'Claude'}")

has_ai = _ai_available(ai_provider, google_key, anthropic_key)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="main-header">🎓 Scholar-Bot</div>'
    '<div class="sub-header">AI resume optimizer · LinkedIn job matcher · Auto-apply</div>',
    unsafe_allow_html=True,
)

if not has_ai:
    st.markdown(
        '<div class="warn-box">⚠️ <b>No API key set.</b> Running in <b>keyword-match mode</b> — '
        'jobs will still be fetched and matched, but AI-powered resume optimisation is disabled. '
        'Add a free Google API key at <a href="https://aistudio.google.com" target="_blank">'
        'aistudio.google.com</a> to unlock full features.</div>',
        unsafe_allow_html=True,
    )

tab_upload, tab_jobs, tab_resume, tab_apply, tab_report = st.tabs([
    "📄 Upload Resume", "💼 Job Matches", "✏️ Optimized Resumes",
    "🚀 Auto Apply", "📊 Report",
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Upload & Pipeline
# ═══════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.markdown("#### Upload your resume")
    uploaded = st.file_uploader(
        "Drag & drop (.pdf .jpg .jpeg .png .svg)",
        type=["pdf","jpg","jpeg","png","svg"],
    )

    c1, c2 = st.columns(2)
    run_full     = c1.button("🚀 Find Jobs + Optimise Resume",
                             type="primary", disabled=not uploaded,
                             use_container_width=True)
    run_analysis = c2.button("🔬 Analyse Resume Only",
                             disabled=not uploaded, use_container_width=True)

    if not uploaded:
        st.info("Upload a resume file above to get started.")

    if (run_full or run_analysis) and uploaded:
        with tempfile.NamedTemporaryFile(delete=False,
                                         suffix=Path(uploaded.name).suffix) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        try:
            # ── Step 1: Parse ────────────────────────────────────────────────
            with st.status("Parsing resume…", expanded=True) as s:
                from src.resume_parser import ResumeParser
                text = ResumeParser().parse(tmp_path)
                if not text.strip():
                    st.error("No text found. Try a clearer scan or PDF.")
                    st.stop()
                st.session_state.resume_text = text
                s.update(label=f"Parsed ({len(text):,} chars)", state="complete")

            # ── Step 2: Extract skills ───────────────────────────────────────
            if has_ai:
                with st.status(f"Extracting skills with AI…", expanded=True) as s:
                    try:
                        ext = _get_extractor(ai_provider, google_key, anthropic_key)
                        rd  = ext.extract_from_resume(text)
                        st.session_state.ai_used = True
                        s.update(label=f"AI extracted {len(rd.get('technical_skills',[]))} skills",
                                 state="complete")
                    except Exception as e:
                        st.warning(f"AI quota hit — switching to keyword mode. ({e})")
                        from src.fallback_extractor import extract_resume
                        rd = extract_resume(text)
                        st.session_state.ai_used = False
                        s.update(label="Keyword extraction (fallback)", state="complete")
            else:
                with st.status("Extracting skills (keyword mode)…", expanded=True) as s:
                    from src.fallback_extractor import extract_resume
                    rd = extract_resume(text)
                    st.session_state.ai_used = False
                    s.update(label="Keyword extraction complete", state="complete")

            st.session_state.resume_data = rd

            # ── ATS audit (always runs after extraction) ─────────────────────
            with st.status("Running ATS audit…", expanded=True) as s:
                ats = _ats_audit(text, rd, has_ai,
                                 ai_provider, google_key, anthropic_key)
                st.session_state["ats_audit"] = ats
                s.update(label=f"ATS score: {ats['score']}/100", state="complete")

            if run_analysis:
                st.success("Resume analysed. Review the ATS audit below.")

            if run_full:
                # ── Step 3: LinkedIn ─────────────────────────────────────────
                skills = (rd.get("technical_skills",[]) + rd.get("tools",[])
                          + rd.get("frameworks",[]))

                # Build search keywords: job title first, then top skills
                if job_title.strip():
                    search_keywords = [job_title.strip()] + skills[:5]
                    search_label    = f'"{job_title.strip()}"'
                else:
                    search_keywords = skills[:10]
                    search_label    = "resume skills"

                with st.status(
                    f"Searching LinkedIn for {search_label} in {location}…",
                    expanded=True
                ) as s:
                    from src.linkedin_scraper import LinkedInScraper
                    jobs = LinkedInScraper().search_jobs(
                        keywords=search_keywords, location=location,
                        num_jobs=num_jobs, days=days_filter,
                        job_title=job_title.strip() if job_title.strip() else None)
                    st.session_state.jobs = jobs
                    s.update(label=f"Found {len(jobs)} job listings", state="complete")

                if not jobs:
                    st.warning("LinkedIn returned no results — may be rate-limiting. "
                               "Try again in a few minutes.")
                    st.stop()

                # ── Step 4: Score ────────────────────────────────────────────
                with st.status("Scoring job matches…", expanded=True) as s:
                    ranked, prog = [], st.progress(0)
                    jobs_with_desc = [j for j in jobs if j.get("description")]

                    for i, job in enumerate(jobs_with_desc):
                        if has_ai and st.session_state.ai_used:
                            try:
                                ext   = _get_extractor(ai_provider, google_key, anthropic_key)
                                reqs  = ext.extract_from_job(job["description"],
                                                             job.get("title",""))
                                analy = ext.calculate_match_score(rd, reqs)
                            except Exception:
                                from src.fallback_extractor import extract_job, score_match
                                reqs  = extract_job(job["description"], job.get("title",""))
                                analy = score_match(rd, reqs)
                        else:
                            from src.fallback_extractor import extract_job, score_match
                            reqs  = extract_job(job["description"], job.get("title",""))
                            analy = score_match(rd, reqs)

                        ranked.append({"job": job, "job_requirements": reqs,
                                       "match_analysis": analy,
                                       "match_score": analy.get("score", 0),
                                       "is_fallback": analy.get("_fallback", False)})
                        prog.progress((i+1) / max(len(jobs_with_desc), 1))

                    ranked.sort(
                        key=lambda x: (
                            x["job"].get("posted_date") or datetime.min,
                            x.get("match_score", 0),
                        ), reverse=True)

                    # ── Apply minimum skill-match filter ──────────────────────
                    before_filter = len(ranked)
                    ranked = [r for r in ranked if r["match_score"] >= min_match_pct]

                    st.session_state.ranked_jobs = ranked
                    filtered_out = before_filter - len(ranked)
                    label = (f"Showing {len(ranked)} jobs ≥{min_match_pct}% match"
                             + (f" ({filtered_out} below threshold hidden)" if filtered_out else ""))
                    s.update(label=label, state="complete")

                # ── Step 5: Bulk optimise top N (AI only) ────────────────────
                if has_ai and st.session_state.ai_used:
                    with st.status(f"Optimising resumes for top {optimize_top} jobs…",
                                   expanded=True) as s:
                        try:
                            opt = _get_optimizer(ai_provider, google_key, anthropic_key)
                            top = opt.bulk_optimize(rd, ranked, top_n=optimize_top)
                            st.session_state.top_optimized = top

                            from src.resume_generator import ResumeGenerator
                            gen = ResumeGenerator()
                            pdf_paths = {}
                            for item in top:
                                jid = item["job"].get("job_id","") or item["job"].get("title","")
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tp:
                                    gen.generate_pdf(item["optimized_resume"], tp.name)
                                    pdf_paths[jid] = tp.name
                            st.session_state.opt_pdf_paths = pdf_paths
                            s.update(label=f"Optimised {len(top)} resumes", state="complete")
                        except Exception as e:
                            st.warning(f"AI optimisation skipped (quota): {e}")
                            s.update(label="Optimisation skipped — use per-job button below",
                                     state="error")
                else:
                    st.info(
                        "AI optimisation not available. Use the **Optimize for this job** "
                        "button on any job card in the **Job Matches** tab."
                    )

            st.success("Done! Check the **Job Matches** tab.")

        finally:
            import os as _os
            _os.unlink(tmp_path)

    # ── Resume snapshot ───────────────────────────────────────────────────────
    if st.session_state.resume_data:
        rd  = st.session_state.resume_data
        ats = st.session_state.get("ats_audit") or {}
        st.divider()
        st.markdown("#### Resume Snapshot"
                    + (" *(keyword mode)*" if rd.get("_fallback") else ""))

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Name",  rd.get("name","—"))
        c2.metric("Role",  rd.get("current_title","—"))
        c3.metric("Exp",   f"{rd.get('experience_years','?')} yrs")
        c4.metric("Email", rd.get("email","—"))

        all_sk = list(dict.fromkeys(
            rd.get("technical_skills",[]) + rd.get("frameworks",[]) + rd.get("tools",[])))
        if all_sk:
            st.markdown("**Detected Skills**")
            st.markdown(
                " ".join(f'<span class="badge badge-blue">{s}</span>' for s in all_sk),
                unsafe_allow_html=True)
        if rd.get("summary"):
            st.info(rd["summary"][:400])

        # ── ATS Score panel ───────────────────────────────────────────────────
        if ats:
            st.divider()
            ats_score = ats.get("score", 0)
            ats_mode  = ats.get("mode","keyword")

            # Score gauge
            col_gauge, col_details = st.columns([1, 2])
            with col_gauge:
                colour = ("#155724" if ats_score>=80
                          else "#856404" if ats_score>=60
                          else "#721c24")
                st.markdown(
                    f"""<div style="text-align:center;background:{'#d4edda' if ats_score>=80
                         else '#fff3cd' if ats_score>=60 else '#f8d7da'};
                         border-radius:16px;padding:1.5rem 1rem">
                    <div style="font-size:3.5rem;font-weight:800;color:{colour};
                                line-height:1">{ats_score}</div>
                    <div style="font-size:1rem;color:{colour};font-weight:600">/ 100</div>
                    <div style="font-size:.8rem;color:#555;margin-top:.3rem">
                        ATS Score {'(AI)' if ats_mode=='ai' else '(keyword)'}</div>
                    </div>""",
                    unsafe_allow_html=True)

            with col_details:
                # What passes
                if ats.get("passed"):
                    st.markdown("**✅ Passing checks**")
                    for p in ats["passed"]:
                        st.markdown(f"&nbsp;&nbsp;✓ {p}")

                # Keyword suggestions (always present)
                if ats.get("suggestions"):
                    st.markdown("**⚠️ Issues to fix**")
                    for s in ats["suggestions"]:
                        st.markdown(f"&nbsp;&nbsp;• {s}")

            # AI-powered deep suggestions
            if ats_mode == "ai":
                st.divider()
                tabs_ats = st.tabs(["🔝 Top Fixes", "📝 Bullet Rewrites",
                                    "🔑 Missing Keywords", "🎨 Format Issues"])

                with tabs_ats[0]:
                    if ats.get("ai_suggestions"):
                        for i, tip in enumerate(ats["ai_suggestions"], 1):
                            st.markdown(f"**{i}.** {tip}")
                    else:
                        st.info("No critical improvements found.")
                    if ats.get("summary_suggestion"):
                        st.markdown("**Suggested Summary:**")
                        st.success(ats["summary_suggestion"])

                with tabs_ats[1]:
                    bullets = ats.get("weak_bullets",[])
                    if bullets:
                        for b in bullets[:8]:
                            if "→" in b:
                                orig, new = b.split("→", 1)
                                st.markdown(f"❌ *{orig.strip()}*")
                                st.markdown(f"✅ **{new.strip()}**")
                                st.divider()
                            else:
                                st.markdown(f"• {b}")
                    else:
                        st.info("Bullet points look good.")

                with tabs_ats[2]:
                    gaps = ats.get("keyword_gaps",[])
                    if gaps:
                        st.markdown(
                            " ".join(f'<span class="badge badge-red">{k}</span>'
                                     for k in gaps),
                            unsafe_allow_html=True)
                        st.caption("Add these keywords (where truthful) to pass ATS filters.")
                    else:
                        st.info("Good keyword coverage.")

                with tabs_ats[3]:
                    issues = ats.get("format_issues",[]) + ats.get("missing_sections",[])
                    if issues:
                        for iss in issues:
                            st.markdown(f"• {iss}")
                    else:
                        st.success("No formatting issues found.")
            else:
                st.caption(
                    "Add a free Gemini API key in the sidebar for AI-powered bullet rewrites, "
                    "keyword gap analysis, and detailed format checks."
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Job Matches
# ═══════════════════════════════════════════════════════════════════════════════
with tab_jobs:
    if not st.session_state.ranked_jobs:
        st.info("Run the pipeline from **Upload Resume** to see job matches.")
    else:
        ranked = st.session_state.ranked_jobs
        rd     = st.session_state.resume_data or {}

        c1,c2,c3 = st.columns([1,1,2])
        min_score = c1.slider("Min Match %", 0, 100, 0, key="minscore")
        show_n    = c2.selectbox("Show", [10,25,50,100], index=1, key="shown")
        search_q  = c3.text_input("Filter title / company", "", key="srch")

        filtered = [
            r for r in ranked
            if r["match_score"] >= min_score
            and (not search_q
                 or search_q.lower() in r["job"].get("title","").lower()
                 or search_q.lower() in r["job"].get("company","").lower())
        ][:show_n]

        if filtered:
            avg = sum(r["match_score"] for r in filtered) / len(filtered)
            m1,m2,m3 = st.columns(3)
            m1.metric("Jobs found", len(ranked))
            m2.metric("Avg match",  f"{avg:.1f}%")
            m3.metric("Best match", f"{max(r['match_score'] for r in filtered):.1f}%")

        if any(r.get("is_fallback") for r in filtered):
            st.markdown(
                '<div class="warn-box">Scores are <b>keyword-based</b> (no AI). '
                'Add a free Gemini key in the sidebar for deeper analysis.</div>',
                unsafe_allow_html=True)

        st.divider()

        for r in filtered:
            job     = r["job"]
            analysis= r["match_analysis"]
            score   = r["match_score"]
            fb      = r.get("is_fallback", False)
            jid     = job.get("job_id","") or job.get("title","")
            jurl    = job.get("url","")

            # ── Job card header ───────────────────────────────────────────────
            st.markdown(
                f'<div class="job-card">'
                f'<b style="font-size:1.05rem">{job.get("title","")}</b>&nbsp;'
                f'{score_badge(score, fb)}<br>'
                f'🏢 <b>{job.get("company","")}</b>&nbsp;&nbsp;'
                f'📍 {job.get("location","")}&nbsp;&nbsp;'
                f'📅 {fmt_date(job.get("posted_date"))}'
                f'</div>',
                unsafe_allow_html=True)

            # ── Action buttons ────────────────────────────────────────────────
            ba, bb, bc = st.columns([2, 2, 1])

            # Apply Now
            if jurl:
                ba.link_button("🔗 Apply Now on LinkedIn", jurl, use_container_width=True)
            else:
                ba.button("🔗 Apply Now", disabled=True, key=f"apply_dis_{jid}",
                          use_container_width=True)

            # Optimize for this job
            opt_clicked = bb.button(
                "✨ Optimize My Resume for This Job",
                key=f"opt_{jid}",
                use_container_width=True,
                disabled=not has_ai,
                help="Requires a Gemini or Anthropic API key" if not has_ai else "",
            )

            # Add to apply queue
            in_queue = any(j.get("job_id") == jid for j in st.session_state.apply_queue)
            if bc.button("➕ Queue" if not in_queue else "✅ Queued",
                         key=f"q_{jid}", disabled=in_queue,
                         use_container_width=True):
                st.session_state.apply_queue.append(job)
                st.rerun()

            # ── Per-job optimisation ──────────────────────────────────────────
            if opt_clicked:
                with st.spinner(f"Optimising resume for {job.get('title')} @ {job.get('company')}…"):
                    try:
                        opt  = _get_optimizer(ai_provider, google_key, anthropic_key)
                        result = opt.optimize_resume(rd, r["job_requirements"],
                                                      r["match_analysis"])
                        st.session_state.per_job_opt[jid] = result
                        st.success("Optimised! Download below.")
                    except Exception as e:
                        st.error(f"Optimisation failed: {e}")

            # ── Show optimised resume if ready ────────────────────────────────
            if jid in st.session_state.per_job_opt:
                opt_res = st.session_state.per_job_opt[jid]
                with st.expander("📄 Optimised Resume — Preview & Download", expanded=True):
                    dc, dd = st.columns(2)

                    # PDF download
                    with dc:
                        try:
                            from src.resume_generator import ResumeGenerator
                            gen = ResumeGenerator()
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tp:
                                gen.generate_pdf(opt_res, tp.name)
                                pdf_bytes = Path(tp.name).read_bytes()
                                import os as _os; _os.unlink(tp.name)
                            st.download_button(
                                "⬇ Download PDF",
                                pdf_bytes,
                                f"resume_{job.get('company','').replace(' ','_')[:12]}.pdf",
                                "application/pdf", key=f"dlpdf_{jid}",
                                use_container_width=True, type="primary")
                        except Exception as e:
                            st.error(f"PDF error: {e}")

                    # Markdown download
                    with dd:
                        from src.resume_generator import ResumeGenerator
                        gen = ResumeGenerator()
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w") as tm:
                            gen.generate_markdown(opt_res, tm.name)
                            md_text = Path(tm.name).read_text()
                            import os as _os; _os.unlink(tm.name)
                        st.download_button(
                            "⬇ Download Markdown", md_text,
                            f"resume_{job.get('company','').replace(' ','_')[:12]}.md",
                            "text/markdown", key=f"dlmd_{jid}",
                            use_container_width=True)

                    # Changes made
                    if opt_res.get("optimization_notes"):
                        st.markdown("**Changes made:**")
                        for n in opt_res["optimization_notes"][:6]:
                            st.markdown(f"✓ {n}")
                    if opt_res.get("added_keywords"):
                        st.markdown(
                            "**Keywords added:** "
                            + " ".join(f'<span class="badge badge-green">{k}</span>'
                                       for k in opt_res["added_keywords"][:10]),
                            unsafe_allow_html=True)

                    # Apply link again, prominently
                    if jurl:
                        st.link_button("🚀 Apply Now with This Resume →", jurl,
                                       use_container_width=True)

            # ── Skills gap ────────────────────────────────────────────────────
            with st.expander("Skills gap"):
                ca,cb = st.columns(2)
                with ca:
                    st.markdown("**Matching**")
                    st.markdown(
                        " ".join(f'<span class="badge badge-green">{s}</span>'
                                 for s in analysis.get("matched_required",[])) or "—",
                        unsafe_allow_html=True)
                with cb:
                    st.markdown("**Missing**")
                    st.markdown(
                        " ".join(f'<span class="badge badge-red">{s}</span>'
                                 for s in analysis.get("missing_required",[])) or "—",
                        unsafe_allow_html=True)

        # ── Bulk add to queue ─────────────────────────────────────────────────
        if filtered:
            st.divider()
            selections = []
            with st.expander("Select multiple jobs for Auto Apply"):
                for r in filtered[:20]:
                    job = r["job"]
                    label = (f"{job.get('title','?')} @ {job.get('company','?')} "
                             f"— {r['match_score']:.0f}%")
                    if st.checkbox(label, key=f"chk_{job.get('job_id',job.get('title',''))}"):
                        selections.append(job)
            if st.button("Add Selected to Apply Queue", type="primary",
                         disabled=not selections):
                existing = {j.get("job_id") for j in st.session_state.apply_queue}
                new = [j for j in selections if j.get("job_id") not in existing]
                st.session_state.apply_queue.extend(new)
                st.success(f"Added {len(new)} jobs → go to **Auto Apply** tab.")

            # Export
            export = [{"rank":i+1,"title":r["job"].get("title"),
                       "company":r["job"].get("company"),
                       "location":r["job"].get("location"),
                       "posted_date":fmt_date(r["job"].get("posted_date")),
                       "match_score":r["match_score"],
                       "url":r["job"].get("url")}
                      for i,r in enumerate(filtered)]
            st.download_button("Download Job List (JSON)",
                               json.dumps(export, indent=2),
                               "scholar_bot_jobs.json", "application/json")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Bulk Optimised Resumes
# ═══════════════════════════════════════════════════════════════════════════════
with tab_resume:
    if not st.session_state.top_optimized:
        st.info(
            "No bulk-optimised resumes yet. Run the full pipeline with an AI key, "
            "or use the **✨ Optimize My Resume for This Job** button on any job card."
        )
    else:
        from src.resume_generator import ResumeGenerator
        gen = ResumeGenerator()

        for i, item in enumerate(st.session_state.top_optimized, 1):
            job = item["job"]; opt = item["optimized_resume"]; score = item.get("match_score",0)
            st.markdown(
                f"#### {i}. {job.get('title')} — {job.get('company')} "
                f"{score_badge(score)}",
                unsafe_allow_html=True)

            ca, cb = st.columns(2)
            # PDF
            with ca:
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tp:
                        gen.generate_pdf(opt, tp.name)
                        pdf_bytes = Path(tp.name).read_bytes()
                        import os as _os; _os.unlink(tp.name)
                    st.download_button("⬇ Download PDF",
                                       pdf_bytes,
                                       f"resume_{job.get('company','').replace(' ','_')[:12]}_{i}.pdf",
                                       "application/pdf",
                                       key=f"bpdf_{i}",
                                       use_container_width=True, type="primary")
                except Exception as e:
                    st.error(f"PDF error: {e}")
            # Markdown
            with cb:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w") as tm:
                    gen.generate_markdown(opt, tm.name)
                    md_text = Path(tm.name).read_text()
                    import os as _os; _os.unlink(tm.name)
                st.download_button("⬇ Download Markdown", md_text,
                                   f"resume_{job.get('company','').replace(' ','_')[:12]}_{i}.md",
                                   "text/markdown", key=f"bmd_{i}",
                                   use_container_width=True)

            if job.get("url"):
                st.link_button("🚀 Apply Now →", job["url"], use_container_width=False)

            with st.expander("Preview changes"):
                cx, cy = st.columns([2,1])
                with cx:
                    st.markdown(f"**Summary:** {opt.get('summary','')}")
                    sk = list(dict.fromkeys(opt.get("technical_skills",[])
                                           + opt.get("frameworks",[])
                                           + opt.get("tools",[])))
                    st.markdown(
                        " ".join(f'<span class="badge badge-blue">{s}</span>' for s in sk),
                        unsafe_allow_html=True)
                with cy:
                    for n in opt.get("optimization_notes",[])[:5]:
                        st.markdown(f"✓ {n}")
                    st.markdown(
                        " ".join(f'<span class="badge badge-green">{k}</span>'
                                 for k in opt.get("added_keywords",[])[:8]),
                        unsafe_allow_html=True)
            st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Auto Apply
# ═══════════════════════════════════════════════════════════════════════════════
with tab_apply:
    st.markdown("### 🚀 Auto Apply")
    st.caption("Scholar-Bot fills every Easy Apply form and pauses for your review before submitting.")

    if not li_email or not li_password:
        st.warning("Enter your LinkedIn credentials in the sidebar.")

    queue = st.session_state.apply_queue
    if not queue:
        st.info("No jobs queued. Use the **➕ Queue** button on job cards in **Job Matches**.")
    else:
        st.markdown(f"**{len(queue)} job(s) in queue:**")
        to_remove = []
        for j in queue:
            c1, c2 = st.columns([5,1])
            c1.markdown(f"• **{j.get('title')}** @ {j.get('company')} — {j.get('location','')}")
            if c2.button("Remove", key=f"rm_{j.get('job_id',j.get('title',''))}"):
                to_remove.append(j)
        for j in to_remove:
            st.session_state.apply_queue.remove(j)
        if to_remove:
            st.rerun()

        st.divider()
        rd       = st.session_state.resume_data
        opt_pdfs = st.session_state.opt_pdf_paths

        def _pick_pdf(job):
            jid = job.get("job_id","")
            return (opt_pdfs.get(jid) or next(iter(opt_pdfs.values()), "")) if opt_pdfs else ""

        can_start = (li_email and li_password and rd
                     and not st.session_state.apply_thread_running)

        if st.button("▶ Start Auto Apply", type="primary", disabled=not can_start):
            from src.auto_apply import AutoApply, ApplicationStatus

            status_map, screenshot_map = {}, {}

            def on_status(job_id, status, screenshot):
                status_map[job_id] = status
                if screenshot:
                    screenshot_map[job_id] = screenshot
                st.session_state.apply_status_map     = dict(status_map)
                st.session_state.apply_screenshot_map = dict(screenshot_map)

            applier = AutoApply(
                email=li_email, password=li_password,
                resume_data=rd, resume_pdf_path=_pick_pdf(queue[0]),
                headless=headless, on_status=on_status)
            st.session_state.applier = applier

            def _run():
                st.session_state.apply_thread_running = True
                st.session_state.apply_results = applier.apply_to_jobs(queue)
                st.session_state.apply_thread_running = False

            threading.Thread(target=_run, daemon=True).start()
            st.info("Auto-apply started. Review status below.")

        if st.session_state.apply_thread_running or st.session_state.apply_results:
            st.divider()
            st.markdown("#### Application Status")
            status_map     = st.session_state.apply_status_map
            screenshot_map = st.session_state.apply_screenshot_map
            applier        = st.session_state.applier

            for job in queue:
                jid    = job.get("job_id","")
                status = status_map.get(jid, "pending")
                colour = {"done":"#155724","failed":"#721c24",
                          "waiting_approval":"#856404"}.get(status,"#004085")
                st.markdown(
                    f'<b style="color:{colour}">{job.get("title")} @ {job.get("company")}</b>'
                    f' — <code>{status.replace("_"," ").upper()}</code>',
                    unsafe_allow_html=True)

                if status == "waiting_approval" and applier:
                    if jid in screenshot_map:
                        img_bytes = base64.b64decode(screenshot_map[jid])
                        st.image(img_bytes, caption="Application preview",
                                 use_container_width=True)
                    st.markdown("**Review the form, then click Submit or Skip.**")
                    b1, b2 = st.columns(2)
                    if b1.button("✅ Submit Application", key=f"sub_{jid}", type="primary"):
                        applier.signal_submit(approve=True)
                        st.success("Submitted!")
                    if b2.button("⏭ Skip", key=f"skip_{jid}"):
                        applier.signal_submit(approve=False)

            if st.session_state.apply_results:
                st.divider()
                st.markdown("#### Results")
                for r in st.session_state.apply_results:
                    icon = {"done":"✅","failed":"❌","skipped":"⏭"}.get(r.get("status",""),"•")
                    st.markdown(f"{icon} **{r.get('title')} @ {r.get('company')}** — "
                                f"{r.get('status','').upper()}"
                                + (f" _{r.get('error','')}_" if r.get("error") else ""))

            if st.session_state.apply_thread_running:
                st.info("Applying… refresh to see updates.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Report
# ═══════════════════════════════════════════════════════════════════════════════
with tab_report:
    if not st.session_state.ranked_jobs:
        st.info("Run the pipeline to generate the report.")
    else:
        ranked = st.session_state.ranked_jobs
        st.markdown(f"### Full Report — {len(ranked)} jobs")

        try:
            import pandas as pd
            scores = [r["match_score"] for r in ranked]
            buckets = {"Excellent (≥80%)": sum(1 for s in scores if s>=80),
                       "Good (60-79%)":    sum(1 for s in scores if 60<=s<80),
                       "Fair (40-59%)":    sum(1 for s in scores if 40<=s<60),
                       "Low (<40%)":       sum(1 for s in scores if s<40)}
            st.bar_chart(pd.DataFrame({"Category":list(buckets.keys()),
                                        "Count":list(buckets.values())}).set_index("Category"))

            rows = [{"#":i,"Title":r["job"].get("title",""),
                     "Company":r["job"].get("company",""),
                     "Location":r["job"].get("location",""),
                     "Posted":fmt_date(r["job"].get("posted_date")),
                     "Match %":f"{r['match_score']:.1f}",
                     "Mode":"AI" if not r.get("is_fallback") else "Keyword",
                     "Apply":r["job"].get("url","")}
                    for i,r in enumerate(ranked,1)]
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("Download CSV", df.to_csv(index=False),
                               "scholar_bot_report.csv", "text/csv")
        except Exception as e:
            st.error(f"Table error: {e}")
