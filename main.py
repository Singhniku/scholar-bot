#!/usr/bin/env python3
"""
Scholar-Bot: AI-powered resume optimizer + LinkedIn job matcher.

Usage:
  python main.py --resume path/to/resume.pdf --location "San Francisco, CA"
  python main.py --resume resume.jpg --location "New York" --jobs 30 --days 7
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Scholar-Bot: ATS resume optimizer + LinkedIn job matcher"
    )
    p.add_argument(
        "--resume", required=True,
        help="Path to resume file (.pdf, .jpg, .jpeg, .png, .svg)"
    )
    p.add_argument(
        "--location", default="United States",
        help="Job search location (default: United States)"
    )
    p.add_argument(
        "--jobs", type=int, default=50,
        help="Number of jobs to fetch from LinkedIn (default: 50)"
    )
    p.add_argument(
        "--days", type=int, default=30, choices=[1, 7, 30],
        help="Recency filter in days: 1, 7, or 30 (default: 30)"
    )
    p.add_argument(
        "--output-dir", default="./output",
        help="Directory for output files (default: ./output)"
    )
    p.add_argument(
        "--optimize-top", type=int, default=3,
        help="Generate ATS-optimized resume for top N matching jobs (default: 3)"
    )
    p.add_argument(
        "--no-linkedin", action="store_true",
        help="Skip LinkedIn scraping (only extract skills and show resume analysis)"
    )
    return p


def main():
    args = build_parser().parse_args()

    provider = os.getenv("AI_PROVIDER", "gemini").lower()
    api_key  = os.getenv("GOOGLE_API_KEY", "") if provider == "gemini" \
               else os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        key_var = "GOOGLE_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY"
        logger.error(
            f"{key_var} is not set. Copy .env.example → .env and add your key.\n"
            "Free Google Gemini key: https://aistudio.google.com"
        )
        sys.exit(1)

    resume_path = args.resume
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── 1. Parse resume ──────────────────────────────────────────────────────
    logger.info(f"Step 1/5 — Parsing resume: {resume_path}")
    from src.resume_parser import ResumeParser
    parser = ResumeParser()
    resume_text = parser.parse(resume_path)
    if not resume_text.strip():
        logger.error("No text could be extracted from the resume. Check file quality.")
        sys.exit(1)
    logger.info(f"Extracted {len(resume_text)} characters from resume")

    # ── 2. Extract skills ────────────────────────────────────────────────────
    from src.ai_client import AIClient
    from src.skills_extractor import SkillsExtractor
    ai = AIClient(provider=provider, api_key=api_key)
    logger.info(f"Step 2/5 — Extracting skills with {ai.provider_label}...")
    extractor = SkillsExtractor(client=ai)
    resume_data = extractor.extract_from_resume(resume_text)

    # LinkedIn profile URL is optional; when present it lands on the generated
    # resume contact line and on the "LinkedIn URL" field of Easy Apply forms.
    linkedin_profile_url = os.getenv("LINKEDIN_PROFILE_URL", "").strip()
    if linkedin_profile_url:
        resume_data["linkedin_url"] = linkedin_profile_url

    skills = (
        resume_data.get("technical_skills", [])
        + resume_data.get("tools", [])
        + resume_data.get("frameworks", [])
    )
    logger.info(f"Found {len(skills)} skills: {', '.join(skills[:12])}...")

    if args.no_linkedin:
        _print_resume_summary(resume_data)
        logger.info("Skipping LinkedIn (--no-linkedin). Done.")
        return

    # ── 3. Scrape LinkedIn ───────────────────────────────────────────────────
    logger.info(
        f"Step 3/5 — Searching LinkedIn for matching jobs "
        f"(location: {args.location}, days: {args.days}, max: {args.jobs})..."
    )
    from src.linkedin_scraper import LinkedInScraper
    scraper = LinkedInScraper()
    jobs = scraper.search_jobs(
        keywords=skills[:10],
        location=args.location,
        num_jobs=args.jobs,
        days=args.days,
    )
    logger.info(f"Retrieved {len(jobs)} jobs from LinkedIn")

    if not jobs:
        logger.warning(
            "No jobs found. LinkedIn may be rate-limiting. "
            "Try again later or use a VPN."
        )
        sys.exit(0)

    # ── 4. Score & rank jobs ─────────────────────────────────────────────────
    logger.info("Step 4/5 — Scoring job matches against resume...")
    ranked_jobs = []
    for job in jobs:
        jd = job.get("description", "")
        if not jd:
            continue
        job_reqs = extractor.extract_from_job(jd, job.get("title", ""))
        analysis = extractor.calculate_match_score(resume_data, job_reqs)
        ranked_jobs.append(
            {
                "job": job,
                "job_requirements": job_reqs,
                "match_analysis": analysis,
                "match_score": analysis.get("score", 0),
            }
        )

    # Sort: primary = posting date desc, secondary = match score desc
    ranked_jobs.sort(
        key=lambda x: (
            x["job"].get("posted_date") or datetime.min,
            x.get("match_score", 0),
        ),
        reverse=True,
    )

    logger.info(
        f"Top match: {ranked_jobs[0]['job']['title']} "
        f"@ {ranked_jobs[0]['job']['company']} "
        f"— {ranked_jobs[0]['match_score']:.1f}%"
        if ranked_jobs else "No scored jobs"
    )

    # ── 5. Optimize resume & generate output ─────────────────────────────────
    logger.info(
        f"Step 5/5 — Generating ATS-optimized resumes for top {args.optimize_top} jobs..."
    )
    from src.ats_optimizer import ATSOptimizer
    from src.resume_generator import ResumeGenerator

    optimizer = ATSOptimizer(client=ai)
    generator = ResumeGenerator()

    top_optimized = optimizer.bulk_optimize(
        resume_data, ranked_jobs, top_n=args.optimize_top
    )

    # Re-attach linkedin_url — ATSOptimizer returns a fresh JSON that doesn't
    # include fields outside its declared schema.
    if linkedin_profile_url:
        for item in top_optimized:
            item["optimized_resume"]["linkedin_url"] = linkedin_profile_url

    for i, item in enumerate(top_optimized, 1):
        job = item["job"]
        opt_resume = item["optimized_resume"]
        company_slug = job.get("company", "company").replace(" ", "_")[:20]
        title_slug = job.get("title", "role").replace(" ", "_")[:20]
        prefix = f"{ts}_{i}_{title_slug}_{company_slug}"

        pdf_path = generator.generate_pdf(opt_resume, str(output_dir / f"{prefix}.pdf"))
        md_path = generator.generate_markdown(opt_resume, str(output_dir / f"{prefix}.md"))
        logger.info(f"  [{i}] {job['title']} @ {job['company']}")
        logger.info(f"       PDF  → {pdf_path}")
        logger.info(f"       MD   → {md_path}")

        if opt_resume.get("optimization_notes"):
            logger.info("       Changes: " + "; ".join(opt_resume["optimization_notes"][:3]))

    # Job report
    report_path = generator.generate_job_report(
        ranked_jobs, str(output_dir / f"{ts}_job_report.md")
    )

    # JSON snapshot
    snapshot_path = output_dir / f"{ts}_analysis.json"
    with open(snapshot_path, "w") as f:
        snapshot = [
            {
                "rank": i,
                "title": r["job"].get("title"),
                "company": r["job"].get("company"),
                "location": r["job"].get("location"),
                "posted_date": (
                    r["job"]["posted_date"].isoformat()
                    if r["job"].get("posted_date")
                    else None
                ),
                "url": r["job"].get("url"),
                "match_score": r["match_score"],
                "missing_required": r["match_analysis"].get("missing_required", []),
                "matched_required": r["match_analysis"].get("matched_required", []),
            }
            for i, r in enumerate(ranked_jobs, 1)
        ]
        json.dump(snapshot, f, indent=2)

    # Console summary
    print("\n" + "=" * 70)
    print("SCHOLAR-BOT RESULTS")
    print("=" * 70)
    print(f"\nResume parsed: {resume_path}")
    print(f"Skills found:  {len(skills)}")
    print(f"Jobs fetched:  {len(jobs)}")
    print(f"Jobs scored:   {len(ranked_jobs)}")
    print(f"\n{'RANK':<5} {'SCORE':>6}  {'DATE':<12}  {'TITLE':<35}  COMPANY")
    print("-" * 80)
    for i, r in enumerate(ranked_jobs[:25], 1):
        job = r["job"]
        posted = job.get("posted_date")
        date_str = posted.strftime("%Y-%m-%d") if posted else "Unknown   "
        title = (job.get("title") or "")[:34]
        company = (job.get("company") or "")[:25]
        print(f"{i:<5} {r['match_score']:>5.1f}%  {date_str:<12}  {title:<35}  {company}")

    print(f"\nOutput directory: {output_dir.resolve()}")
    print(f"  • Job report:   {report_path}")
    print(f"  • Analysis JSON: {snapshot_path}")
    print(f"  • Optimized resumes: {args.optimize_top} PDF+MD files")
    print("=" * 70)


def _print_resume_summary(resume_data: dict):
    print("\n" + "=" * 60)
    print("RESUME ANALYSIS")
    print("=" * 60)
    print(f"Name:      {resume_data.get('name', 'N/A')}")
    print(f"Title:     {resume_data.get('current_title', 'N/A')}")
    print(f"Location:  {resume_data.get('location', 'N/A')}")
    print(f"Experience:{resume_data.get('experience_years', 'N/A')} years")
    print(f"\nTechnical Skills ({len(resume_data.get('technical_skills', []))}):")
    print("  " + ", ".join(resume_data.get("technical_skills", [])[:15]))
    print(f"\nTools: {', '.join(resume_data.get('tools', [])[:10])}")
    print(f"Frameworks: {', '.join(resume_data.get('frameworks', [])[:10])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
