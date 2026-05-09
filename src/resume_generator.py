import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ResumeGenerator:
    """Generates ATS-friendly PDF and Markdown resumes from structured data."""

    # Fonts and colors
    _HEADING_FONT = "Helvetica-Bold"
    _BODY_FONT = "Helvetica"
    _ACCENT = (0.12, 0.29, 0.53)  # RGB 0-1 scale — dark blue
    _BLACK = (0.1, 0.1, 0.1)

    def generate_pdf(self, resume_data: dict[str, Any], output_path: str) -> str:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, HRFlowable, ListFlowable, ListItem
            )
        except ImportError:
            raise ImportError("reportlab is required: pip install reportlab")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=0.65 * inch,
            rightMargin=0.65 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )

        accent = colors.Color(*self._ACCENT)
        black = colors.Color(*self._BLACK)

        styles = getSampleStyleSheet()

        name_style = ParagraphStyle(
            "Name",
            fontName=self._HEADING_FONT,
            fontSize=22,
            textColor=accent,
            spaceAfter=2,
            leading=26,
        )
        contact_style = ParagraphStyle(
            "Contact",
            fontName=self._BODY_FONT,
            fontSize=9,
            textColor=black,
            spaceAfter=4,
        )
        section_style = ParagraphStyle(
            "Section",
            fontName=self._HEADING_FONT,
            fontSize=11,
            textColor=accent,
            spaceBefore=8,
            spaceAfter=2,
            leading=14,
        )
        job_title_style = ParagraphStyle(
            "JobTitle",
            fontName=self._HEADING_FONT,
            fontSize=10,
            textColor=black,
            spaceAfter=1,
            leading=13,
        )
        sub_style = ParagraphStyle(
            "Sub",
            fontName=self._BODY_FONT,
            fontSize=9,
            textColor=colors.Color(0.35, 0.35, 0.35),
            spaceAfter=1,
            leading=12,
        )
        body_style = ParagraphStyle(
            "Body",
            fontName=self._BODY_FONT,
            fontSize=9.5,
            textColor=black,
            spaceAfter=2,
            leading=13,
        )
        bullet_style = ParagraphStyle(
            "Bullet",
            fontName=self._BODY_FONT,
            fontSize=9.5,
            textColor=black,
            spaceAfter=1,
            leftIndent=12,
            leading=13,
        )

        story = []

        # Header
        story.append(Paragraph(resume_data.get("name", ""), name_style))
        contact_parts = [
            p for p in [
                resume_data.get("email", ""),
                resume_data.get("phone", ""),
                resume_data.get("location", ""),
                resume_data.get("linkedin_url", ""),
            ] if p
        ]
        story.append(Paragraph(" | ".join(contact_parts), contact_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=accent))

        # Summary
        if resume_data.get("summary"):
            story.append(Paragraph("PROFESSIONAL SUMMARY", section_style))
            story.append(Paragraph(resume_data["summary"], body_style))
            story.append(HRFlowable(width="100%", thickness=0.5, color=accent))

        # Skills
        self._add_skills_section(story, resume_data, section_style, body_style, accent)

        # Experience
        if resume_data.get("experience"):
            story.append(Paragraph("WORK EXPERIENCE", section_style))
            story.append(HRFlowable(width="100%", thickness=0.5, color=accent))
            for exp in resume_data["experience"]:
                story.append(
                    Paragraph(
                        f"{exp.get('title', '')} — {exp.get('company', '')}",
                        job_title_style,
                    )
                )
                story.append(Paragraph(exp.get("duration", ""), sub_style))
                for ach in exp.get("achievements", []):
                    story.append(Paragraph(f"• {ach}", bullet_style))
                story.append(Spacer(1, 4))

        # Projects
        if resume_data.get("projects"):
            story.append(Paragraph("PROJECTS", section_style))
            story.append(HRFlowable(width="100%", thickness=0.5, color=accent))
            for proj in resume_data["projects"]:
                techs = ", ".join(proj.get("technologies", []))
                title = proj.get("name", "")
                story.append(
                    Paragraph(f"<b>{title}</b>  <font size='8'>[{techs}]</font>", body_style)
                )
                if proj.get("description"):
                    story.append(Paragraph(f"• {proj['description']}", bullet_style))
                story.append(Spacer(1, 3))

        # Education
        if resume_data.get("education"):
            story.append(Paragraph("EDUCATION", section_style))
            story.append(HRFlowable(width="100%", thickness=0.5, color=accent))
            for edu in resume_data["education"]:
                degree = edu.get("degree", "")
                inst = edu.get("institution", "")
                year = edu.get("year", "")
                story.append(
                    Paragraph(f"<b>{degree}</b> — {inst}  {year}", body_style)
                )

        # Certifications
        if resume_data.get("certifications"):
            story.append(Paragraph("CERTIFICATIONS", section_style))
            story.append(HRFlowable(width="100%", thickness=0.5, color=accent))
            for cert in resume_data["certifications"]:
                story.append(Paragraph(f"• {cert}", bullet_style))

        doc.build(story)
        logger.info(f"PDF resume saved: {output_path}")
        return output_path

    def _add_skills_section(self, story, resume_data, section_style, body_style, accent):
        from reportlab.platypus import HRFlowable, Paragraph

        all_skills = []
        for key in ("technical_skills", "frameworks", "tools", "languages"):
            all_skills.extend(resume_data.get(key, []))
        soft = resume_data.get("soft_skills", [])

        if not all_skills and not soft:
            return

        story.append(Paragraph("SKILLS", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=accent))

        if all_skills:
            story.append(
                Paragraph(
                    f"<b>Technical:</b> {', '.join(dict.fromkeys(all_skills))}",
                    body_style,
                )
            )
        if soft:
            story.append(
                Paragraph(f"<b>Soft Skills:</b> {', '.join(soft)}", body_style)
            )

    def generate_markdown(self, resume_data: dict[str, Any], output_path: str) -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        lines = []

        lines.append(f"# {resume_data.get('name', '')}")
        contact = " | ".join(
            p for p in [
                resume_data.get("email", ""),
                resume_data.get("phone", ""),
                resume_data.get("location", ""),
                resume_data.get("linkedin_url", ""),
            ] if p
        )
        lines.append(contact)
        lines.append("")

        if resume_data.get("summary"):
            lines.append("## Professional Summary")
            lines.append(resume_data["summary"])
            lines.append("")

        # Skills
        all_tech = []
        for key in ("technical_skills", "frameworks", "tools", "languages"):
            all_tech.extend(resume_data.get(key, []))
        if all_tech:
            lines.append("## Skills")
            lines.append(f"**Technical:** {', '.join(dict.fromkeys(all_tech))}")
            if resume_data.get("soft_skills"):
                lines.append(f"**Soft Skills:** {', '.join(resume_data['soft_skills'])}")
            lines.append("")

        if resume_data.get("experience"):
            lines.append("## Work Experience")
            for exp in resume_data["experience"]:
                lines.append(f"### {exp.get('title', '')} — {exp.get('company', '')}")
                lines.append(f"*{exp.get('duration', '')}*")
                for ach in exp.get("achievements", []):
                    lines.append(f"- {ach}")
                lines.append("")

        if resume_data.get("projects"):
            lines.append("## Projects")
            for proj in resume_data["projects"]:
                techs = ", ".join(proj.get("technologies", []))
                lines.append(f"### {proj.get('name', '')} `[{techs}]`")
                if proj.get("description"):
                    lines.append(proj["description"])
                lines.append("")

        if resume_data.get("education"):
            lines.append("## Education")
            for edu in resume_data["education"]:
                lines.append(
                    f"**{edu.get('degree', '')}** — {edu.get('institution', '')}  {edu.get('year', '')}"
                )
            lines.append("")

        if resume_data.get("certifications"):
            lines.append("## Certifications")
            for cert in resume_data["certifications"]:
                lines.append(f"- {cert}")
            lines.append("")

        content = "\n".join(lines)
        Path(output_path).write_text(content, encoding="utf-8")
        logger.info(f"Markdown resume saved: {output_path}")
        return output_path

    def generate_job_report(
        self, jobs_ranked: list[dict[str, Any]], output_path: str
    ) -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Job Opportunities Report",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            f"*Total jobs found: {len(jobs_ranked)}*",
            "",
            "---",
            "",
        ]

        for i, item in enumerate(jobs_ranked, 1):
            job = item.get("job", {})
            posted = job.get("posted_date")
            date_str = posted.strftime("%Y-%m-%d") if posted else "Unknown"
            score = item.get("match_score", 0)
            match_label = (
                "Excellent" if score >= 80
                else "Good" if score >= 60
                else "Fair" if score >= 40
                else "Low"
            )

            lines.append(f"## {i}. {job.get('title', 'Unknown Title')}")
            lines.append(f"**Company:** {job.get('company', 'N/A')}")
            lines.append(f"**Location:** {job.get('location', 'N/A')}")
            lines.append(f"**Posted:** {date_str}")
            lines.append(
                f"**Match Score:** {score:.1f}% ({match_label})"
            )
            if job.get("url"):
                lines.append(f"**Apply:** [{job['url']}]({job['url']})")

            analysis = item.get("match_analysis", {})
            if analysis.get("matched_required"):
                lines.append(
                    f"**Matching Skills:** {', '.join(analysis['matched_required'][:10])}"
                )
            if analysis.get("missing_required"):
                lines.append(
                    f"**Skills to Highlight:** {', '.join(analysis['missing_required'][:5])}"
                )

            lines.append("")
            lines.append("---")
            lines.append("")

        content = "\n".join(lines)
        Path(output_path).write_text(content, encoding="utf-8")
        logger.info(f"Job report saved: {output_path}")
        return output_path
